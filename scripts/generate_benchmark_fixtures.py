"""Generate the synthetic benchmark contract fixtures (PDF + DOCX + ground truth)
from data/benchmark/segmentation/contract_source.json.

Both files are rendered from the same source JSON so segmentation results on
either format can be checked against the same ground truth. Re-run this
script whenever contract_source.json changes.

Usage:
    python scripts/generate_benchmark_fixtures.py
"""

import json
from pathlib import Path

import docx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "data" / "benchmark" / "segmentation"
SOURCE_PATH = BENCHMARK_DIR / "contract_source.json"


def _load_source() -> dict:
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def generate_docx(source: dict, out_path: Path) -> None:
    document = docx.Document()
    document.add_heading(source["title"], level=1)
    document.add_paragraph(source["parties_preamble"])
    for clause in source["clauses"]:
        document.add_heading(f"{clause['section']} {clause['heading']}", level=2)
        document.add_paragraph(clause["body"])
    document.save(str(out_path))


def generate_pdf(source: dict, out_path: Path) -> None:
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = ParagraphStyle(
        "ClauseHeading", parent=styles["Heading2"], spaceBefore=14, spaceAfter=4
    )
    body_style = ParagraphStyle("ClauseBody", parent=styles["BodyText"], spaceAfter=10)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story = [Paragraph(source["title"], title_style), Spacer(1, 12)]
    story.append(Paragraph(source["parties_preamble"], body_style))
    for clause in source["clauses"]:
        story.append(Paragraph(f"{clause['section']} {clause['heading']}", heading_style))
        story.append(Paragraph(clause["body"], body_style))
    doc.build(story)


def generate_ground_truth(source: dict, out_path: Path) -> None:
    ground_truth = {
        "_provenance": (
            "Manually authored ground truth for the synthetic benchmark contract "
            "in contract_source.json. Exact by construction, not extracted or "
            "guessed - each clause below matches what generate_benchmark_fixtures.py "
            "rendered into the PDF/DOCX."
        ),
        "expected_clause_count": len(source["clauses"]),
        "clauses": [
            {
                "position": i + 1,
                "section": clause["section"],
                "heading": clause["heading"],
                "clause_type": clause["clause_type"],
            }
            for i, clause in enumerate(source["clauses"])
        ],
    }
    out_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    source = _load_source()
    generate_docx(source, BENCHMARK_DIR / "sample_contract_de.docx")
    generate_pdf(source, BENCHMARK_DIR / "sample_contract_de.pdf")
    generate_ground_truth(source, BENCHMARK_DIR / "ground_truth.json")
    print(f"Wrote fixtures to {BENCHMARK_DIR}")


if __name__ == "__main__":
    main()
