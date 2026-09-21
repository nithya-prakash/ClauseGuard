"""PDF report generation (spec section 19).

Deliberately plain/functional styling - spec section 19 explicitly says
"Do not make the report look like an official legal opinion." No seals,
letterhead, or formal legal-document conventions; the AI-assisted framing
and disclaimer appear on every page, not just the cover.

Every number in the executive summary is computed from the actual
DocumentAnalysisResult passed in - nothing here is a template placeholder.
"""

import io
from collections import Counter
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.pipeline import DocumentAnalysisResult

DISCLAIMER_TEXT = (
    "ClauseGuard provides AI-assisted first-pass compliance analysis and does "
    "not constitute legal advice. It does not determine whether a contract is "
    "legally valid. Always consult a qualified lawyer for legal decisions."
)

RISK_COLORS = {
    "LOW": colors.HexColor("#16a34a"),
    "MEDIUM": colors.HexColor("#d97706"),
    "HIGH": colors.HexColor("#dc2626"),
    "INSUFFICIENT_EVIDENCE": colors.HexColor("#6b7280"),
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": base["Title"],
        "h1": ParagraphStyle("H1", parent=base["Heading1"], spaceBefore=14, spaceAfter=6),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("Body", parent=base["BodyText"], spaceAfter=6),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontSize=8, textColor=colors.grey
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontSize=9,
            leftIndent=12,
            textColor=colors.HexColor("#374151"),
            spaceAfter=4,
        ),
        "disclaimer": ParagraphStyle(
            "Disclaimer",
            parent=base["BodyText"],
            fontSize=8,
            textColor=colors.HexColor("#92400e"),
            backColor=colors.HexColor("#fffbeb"),
            borderColor=colors.HexColor("#fcd34d"),
            borderWidth=0.5,
            borderPadding=6,
        ),
    }


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, DISCLAIMER_TEXT)
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def _executive_summary(result: DocumentAnalysisResult) -> Counter[str]:
    """Real counts, not estimates - one bucket per clause, computed from the
    actual per-clause outcome so the total always equals clause_count."""
    counts: Counter[str] = Counter()
    for ca in result.clauses:
        if ca.reasoning is not None:
            counts[ca.reasoning.risk_level] += 1
        elif ca.reasoning_error and "ANTHROPIC_API_KEY" in ca.reasoning_error:
            counts["LLM_NOT_CONFIGURED"] += 1
        else:
            counts["PIPELINE_ERROR"] += 1
    return counts


def generate_report_pdf(result: DocumentAnalysisResult, scope: dict[str, Any]) -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,
    )

    story: list[Any] = []

    story.append(Paragraph("ClauseGuard Compliance Screening Report", styles["title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(DISCLAIMER_TEXT, styles["disclaimer"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Document", styles["h1"]))
    meta_table = Table(
        [
            ["Filename", result.filename],
            ["Analyzed at", result.analyzed_at],
            ["Clauses detected", str(result.clause_count)],
        ],
        colWidths=[4 * cm, 12 * cm],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)

    story.append(Paragraph("Supported Legal Scope", styles["h1"]))
    story.append(
        Paragraph(
            f"Jurisdiction: {scope.get('jurisdiction', 'unknown')}. "
            f"Sources: {', '.join(scope.get('sources', []))}. "
            "This analysis is limited to the provisions listed below - a clause "
            "outside this scope is reported as evidence-insufficient, not "
            "assessed as compliant or non-compliant.",
            styles["body"],
        )
    )
    for cs in scope.get("covered_sections", []):
        line = f"&bull; {cs['source']} {cs['section']} &mdash; {cs['title']}"
        story.append(Paragraph(line, styles["quote"]))

    story.append(Paragraph("Executive Summary", styles["h1"]))
    summary_counts = _executive_summary(result)
    summary_rows = [["Outcome", "Clause count"]]
    summary_labels = (
        "LOW",
        "MEDIUM",
        "HIGH",
        "INSUFFICIENT_EVIDENCE",
        "LLM_NOT_CONFIGURED",
        "PIPELINE_ERROR",
    )
    for label in summary_labels:
        if summary_counts.get(label):
            summary_rows.append([label.replace("_", " "), str(summary_counts[label])])
    summary_table = Table(summary_rows, colWidths=[10 * cm, 4 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    story.append(summary_table)
    story.append(
        Paragraph(
            "Risk levels are an AI-generated screening signal, not a legal "
            "conclusion. LLM_NOT_CONFIGURED means the system honestly could not "
            "reason about that clause (no configured LLM), not that it is safe.",
            styles["small"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("Clause-by-Clause Findings", styles["h1"]))

    for ca in sorted(result.clauses, key=lambda c: c.clause.position):
        block: list[Any] = []
        heading = ca.clause.section or f"Clause {ca.clause.position}"
        if ca.clause.heading:
            heading += f" &mdash; {ca.clause.heading}"
        block.append(Paragraph(heading, styles["h2"]))

        classification_text = (
            ca.classification.clause_type if ca.classification else "unavailable"
        )
        block.append(Paragraph(f"<b>Classification:</b> {classification_text}", styles["body"]))

        if ca.reasoning is not None:
            risk = ca.reasoning.risk_level
            risk_color = RISK_COLORS.get(risk, colors.black).hexval()
            block.append(
                Paragraph(
                    f'<b>Risk level:</b> <font color="{risk_color}">{risk}</font> '
                    f"(status: {ca.reasoning.status})",
                    styles["body"],
                )
            )
            block.append(Paragraph(ca.reasoning.explanation, styles["body"]))
            for finding in ca.reasoning.findings:
                citation_color = (
                    "#16a34a" if finding.citation_status == "VERIFIED" else "#dc2626"
                )
                block.append(
                    Paragraph(
                        f"<b>AI finding:</b> {finding.claim} "
                        f'[<font color="{citation_color}">{finding.citation_status}</font>]',
                        styles["quote"],
                    )
                )
                block.append(
                    Paragraph(
                        f"<b>Legal source:</b> {finding.citation} &mdash; {finding.legal_basis}",
                        styles["quote"],
                    )
                )
                evidence_line = f"<b>Evidence:</b> &ldquo;{finding.evidence}&rdquo;"
                block.append(Paragraph(evidence_line, styles["quote"]))
            if ca.reasoning.limitations:
                for limitation in ca.reasoning.limitations:
                    block.append(Paragraph(f"Limitation: {limitation}", styles["small"]))
        elif ca.reasoning_error:
            block.append(
                Paragraph(f"<b>Reasoning not available:</b> {ca.reasoning_error}", styles["small"])
            )

        block.append(Spacer(1, 10))
        story.append(KeepTogether(block))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
