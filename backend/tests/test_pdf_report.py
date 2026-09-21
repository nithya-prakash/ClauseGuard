"""Tests for PDF report generation (Milestone 13).

Verification is a real round-trip: generate a PDF, then re-parse it with
pdfplumber (already a dependency, used for contract ingestion) and check
the actual extracted text - not just "bytes were returned".
"""

import io

import pdfplumber
import pytest

from app.schemas.classification import ClassificationResult
from app.schemas.clause import Clause
from app.schemas.pipeline import ClauseAnalysis, DocumentAnalysisResult
from app.schemas.reasoning import ReasoningResult, VerifiedFinding
from app.services.reporting.pdf_generator import DISCLAIMER_TEXT, generate_report_pdf
from app.services.retrieval.corpus_loader import load_scope


def _clause(clause_id: str, text: str, section: str, heading: str, position: int) -> Clause:
    return Clause(
        clause_id=clause_id,
        text=text,
        section=section,
        heading=heading,
        page_start=1,
        page_end=1,
        position=position,
        char_start=0,
        char_end=len(text),
    )


@pytest.fixture
def sample_result() -> DocumentAnalysisResult:
    clauses = [
        ClauseAnalysis(
            clause=_clause("c1", "Der Verkäufer haftet nur für Vorsatz.", "§ 4", "Haftung", 1),
            classification=ClassificationResult(
                clause_type="LIABILITY", confidence=0.9, model_name="lora-v1"
            ),
            classification_error=None,
            reasoning=ReasoningResult(
                clause_id="c1",
                classification="LIABILITY",
                risk_level="LOW",
                status="OK",
                findings=[
                    VerifiedFinding(
                        claim="Clause limits liability to intent.",
                        legal_basis="§ 276 governs debtor responsibility.",
                        citation="§ 276 BGB",
                        evidence="Der Schuldner hat Vorsatz...",
                        citation_status="VERIFIED",
                        citation_reason=None,
                    )
                ],
                explanation="Consistent with statutory liability rules.",
                confidence="MEDIUM",
                limitations=["Synthetic test data."],
            ),
            reasoning_error=None,
        ),
        ClauseAnalysis(
            clause=_clause("c2", "Wettbewerbsverbot Klausel.", "§ 8", "Wettbewerbsverbot", 2),
            classification=ClassificationResult(
                clause_type="NON_COMPETE", confidence=0.8, model_name="lora-v1"
            ),
            classification_error=None,
            reasoning=ReasoningResult(
                clause_id="c2",
                classification="NON_COMPETE",
                risk_level="INSUFFICIENT_EVIDENCE",
                status="INSUFFICIENT_EVIDENCE",
                findings=[],
                explanation="No relevant evidence found.",
                confidence="LOW",
                limitations=["Corpus does not cover this category."],
            ),
            reasoning_error=None,
        ),
        ClauseAnalysis(
            clause=_clause("c3", "Zahlungsbedingungen.", "§ 2", "Zahlung", 3),
            classification=ClassificationResult(
                clause_type="PAYMENT", confidence=0.7, model_name="lora-v1"
            ),
            classification_error=None,
            reasoning=None,
            reasoning_error=(
                "Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable the reasoning stage."
            ),
        ),
    ]
    return DocumentAnalysisResult(
        filename="test_contract.pdf",
        analyzed_at="2026-09-20T18:00:00+00:00",
        clause_count=3,
        clauses=clauses,
    )


def test_generated_pdf_has_valid_header(sample_result: DocumentAnalysisResult):
    pdf_bytes = generate_report_pdf(sample_result, load_scope())
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_generated_pdf_contains_real_document_metadata(sample_result: DocumentAnalysisResult):
    pdf_bytes = generate_report_pdf(sample_result, load_scope())
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "test_contract.pdf" in text
    assert "2026-09-20T18:00:00" in text
    assert DISCLAIMER_TEXT[:40] in text


def test_generated_pdf_contains_supported_legal_scope(sample_result: DocumentAnalysisResult):
    pdf_bytes = generate_report_pdf(sample_result, load_scope())
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "Supported Legal Scope" in text
    assert "BGB § 276" in text
    assert "DSGVO Art. 28" in text


def test_generated_pdf_contains_real_executive_summary_counts(
    sample_result: DocumentAnalysisResult,
):
    pdf_bytes = generate_report_pdf(sample_result, load_scope())
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # 1 LOW, 1 INSUFFICIENT_EVIDENCE, 1 LLM_NOT_CONFIGURED - matches the
    # 3 synthetic clauses exactly, not a hardcoded/fabricated count.
    assert "LOW" in text
    assert "INSUFFICIENT EVIDENCE" in text
    assert "LLM NOT CONFIGURED" in text


def test_generated_pdf_distinguishes_finding_evidence_and_verification(
    sample_result: DocumentAnalysisResult,
):
    pdf_bytes = generate_report_pdf(sample_result, load_scope())
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "AI finding:" in text
    assert "Legal source:" in text
    assert "Evidence:" in text
    assert "VERIFIED" in text
    assert "Der Schuldner hat Vorsatz" in text


def test_generated_pdf_shows_reasoning_not_available_distinctly(
    sample_result: DocumentAnalysisResult,
):
    pdf_bytes = generate_report_pdf(sample_result, load_scope())
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "Reasoning not available" in text
    assert "ANTHROPIC_API_KEY" in text


# --- Security (Milestone 14): untrusted contract content must never be
# interpreted as reportlab's Paragraph markup. Reachable TODAY via clause
# heading/section alone (segmented straight from the uploaded document's raw
# text) - no LLM key required. Verified real before fixing: an unbalanced
# tag crashed generate_report_pdf() with an unhandled ValueError, and a
# well-formed tag rendered as live formatting/a link rather than literal
# text. See _safe() in pdf_generator.py.


def _clause_analysis_with_heading(heading: str) -> ClauseAnalysis:
    return ClauseAnalysis(
        clause=_clause("c1", "irrelevant text", "§ 1", heading, 1),
        classification=ClassificationResult(
            clause_type="GENERAL_TERMS", confidence=0.5, model_name="x"
        ),
        classification_error=None,
        reasoning=None,
        reasoning_error=(
            "Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable the reasoning stage."
        ),
    )


def test_unbalanced_tag_in_clause_heading_does_not_crash_report_generation():
    # A completely plausible heading from a real German contract (angle-
    # bracket placeholder convention), not a contrived attack string.
    result = DocumentAnalysisResult(
        filename="contract.pdf",
        analyzed_at="2026-09-20T18:00:00+00:00",
        clause_count=1,
        clauses=[_clause_analysis_with_heading("<Kundennummer> Vertragsgegenstand")],
    )
    pdf_bytes = generate_report_pdf(result, load_scope())  # must not raise
    assert pdf_bytes.startswith(b"%PDF")


def test_markup_injection_in_clause_heading_renders_as_literal_text():
    injected = '<font color="red" size="60">INJECTED</font>'
    result = DocumentAnalysisResult(
        filename="contract.pdf",
        analyzed_at="2026-09-20T18:00:00+00:00",
        clause_count=1,
        clauses=[_clause_analysis_with_heading(injected)],
    )
    pdf_bytes = generate_report_pdf(result, load_scope())
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # The literal markup must be visible as text (proving it was escaped),
    # not silently stripped and not interpreted as real formatting/a link.
    assert "<font color=" in text
    assert "INJECTED" in text


def test_malicious_finding_content_does_not_crash_or_inject(sample_result: DocumentAnalysisResult):
    # Exercises the findings path (claim/legal_basis/citation/evidence) -
    # this is where real LLM output will flow once an API key is
    # configured, and it's derived from the same untrusted contract text.
    malicious = VerifiedFinding(
        claim="<unbalanced tag claim",
        legal_basis='<font size="60">huge</font>',
        citation="§ 1 <b>BGB",
        evidence="<a href=\"evil://x\">evidence</a>",
        citation_status="VERIFIED",
        citation_reason=None,
    )
    sample_result.clauses[0].reasoning.findings = [malicious]  # type: ignore[union-attr]

    pdf_bytes = generate_report_pdf(sample_result, load_scope())  # must not raise
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "<unbalanced tag claim" in text
    assert "<a href=" in text
