import json
from pathlib import Path

from app.schemas.document import NormalizedDocument, PageOffset
from app.services.ingestion.service import ingest_document
from app.services.segmentation.segmenter import segment_document

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = REPO_ROOT / "data" / "benchmark" / "segmentation"


def _ground_truth() -> dict:
    return json.loads((BENCHMARK_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def test_segment_pdf_matches_ground_truth():
    gt = _ground_truth()
    doc = ingest_document(BENCHMARK_DIR / "sample_contract_de.pdf")
    clauses = segment_document(doc)

    assert len(clauses) == gt["expected_clause_count"]
    for clause, expected in zip(clauses, gt["clauses"], strict=True):
        assert clause.section == expected["section"]
        assert clause.heading == expected["heading"]
        assert clause.position == expected["position"]


def test_segment_docx_matches_ground_truth():
    gt = _ground_truth()
    doc = ingest_document(BENCHMARK_DIR / "sample_contract_de.docx")
    clauses = segment_document(doc)

    assert len(clauses) == gt["expected_clause_count"]
    for clause, expected in zip(clauses, gt["clauses"], strict=True):
        assert clause.section == expected["section"]


def test_clause_spans_correctly_attributed_across_page_break():
    doc = ingest_document(BENCHMARK_DIR / "sample_contract_de.pdf")
    clauses = segment_document(doc)

    # § 1-7 fall on page 1, § 8-10 on page 2 (verified by manual inspection
    # of the generated fixture); a clause must never claim a page range that
    # doesn't overlap where its text actually landed.
    assert clauses[0].page_start == 1
    assert clauses[-1].page_end == 2


def test_paragraph_fallback_when_no_numbering_present():
    text = "Erster Absatz ohne Nummerierung.\n\nZweiter Absatz, ebenfalls ohne Nummerierung."
    doc = NormalizedDocument(
        filename="plain.txt",
        file_type="docx",
        full_text=text,
        page_offsets=[PageOffset(page_number=1, start=0, end=len(text))],
        pagination_available=False,
    )
    clauses = segment_document(doc)
    assert len(clauses) == 2
    assert clauses[0].section is None
    assert "Erster Absatz" in clauses[0].text
    assert "Zweiter Absatz" in clauses[1].text


def test_wrapped_quantity_line_is_not_a_clause_boundary():
    from app.services.segmentation.patterns import CLAUSE_START_PATTERNS

    def starts_clause(line: str) -> bool:
        return any(p.match(line) for p in CLAUSE_START_PATTERNS)

    assert not starts_clause("50 Prozent innerhalb von zehn Tagen nach Vertragsschluss")
    assert not starts_clause("14 Tage nach Zugang der Rechnung")
    assert starts_clause("3.1 Laufzeit")
    assert starts_clause("2. Zahlung")
