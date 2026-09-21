from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.core.exceptions import OCRNotImplementedError, UnsupportedFileTypeError
from app.services.ingestion.service import ingest_document

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = REPO_ROOT / "data" / "benchmark" / "segmentation"


def test_parse_pdf_extracts_real_text_and_pages():
    doc = ingest_document(BENCHMARK_DIR / "sample_contract_de.pdf")
    assert doc.file_type == "pdf"
    assert doc.pagination_available is True
    assert len(doc.page_offsets) == 2
    assert "Vertragsgegenstand" in doc.full_text
    assert "Haftung" in doc.full_text


def test_parse_docx_extracts_real_text_single_logical_page():
    doc = ingest_document(BENCHMARK_DIR / "sample_contract_de.docx")
    assert doc.file_type == "docx"
    assert doc.pagination_available is False
    assert len(doc.page_offsets) == 1
    assert "Vertraulichkeit" in doc.full_text


def test_unsupported_file_type_raises(tmp_path: Path):
    bogus = tmp_path / "contract.txt"
    bogus.write_text("irrelevant")
    with pytest.raises(UnsupportedFileTypeError):
        ingest_document(bogus)


def test_scanned_pdf_raises_ocr_not_implemented(tmp_path: Path):
    # A PDF with only a couple of short lines of text per page, well below
    # MIN_AVG_CHARS_PER_PAGE, simulating an image-only/scanned document.
    scanned = tmp_path / "scanned.pdf"
    c = canvas.Canvas(str(scanned), pagesize=A4)
    for _ in range(2):
        c.drawString(50, 800, "x")
        c.showPage()
    c.save()

    with pytest.raises(OCRNotImplementedError):
        ingest_document(scanned)
