import zipfile
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.core.exceptions import (
    OCRNotImplementedError,
    UnsupportedFileTypeError,
    ValidationFailedError,
)
from app.services.ingestion import docx_parser, pdf_parser
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


def test_corrupted_pdf_raises_clean_validation_error_not_library_exception(tmp_path: Path):
    # Milestone 14: a malformed upload (real files people accidentally
    # upload - truncated, wrong format renamed, etc.) must not leak a raw
    # third-party library exception (pdfminer.PdfminerException) up to the
    # generic 500 handler; it's a bad-input case (422), not a server bug.
    corrupted = tmp_path / "corrupted.pdf"
    corrupted.write_bytes(b"not a real pdf file, just garbage bytes")
    with pytest.raises(ValidationFailedError) as exc_info:
        ingest_document(corrupted)
    assert exc_info.value.status_code == 422
    assert "PDF" in exc_info.value.detail
    # No internal library/file-path details leaked into the user-facing message.
    assert "pdfminer" not in exc_info.value.detail.lower()
    assert str(corrupted) not in exc_info.value.detail


def test_corrupted_docx_raises_clean_validation_error_not_library_exception(tmp_path: Path):
    corrupted = tmp_path / "corrupted.docx"
    corrupted.write_bytes(b"not a real docx file, just garbage bytes")
    with pytest.raises(ValidationFailedError) as exc_info:
        ingest_document(corrupted)
    assert exc_info.value.status_code == 422
    assert "DOCX" in exc_info.value.detail
    assert str(corrupted) not in exc_info.value.detail


def test_docx_exceeding_uncompressed_size_cap_is_rejected(tmp_path: Path, monkeypatch):
    # Milestone 16 Phase 17: a real zip-bomb defense - checked via the
    # zip's own central directory metadata (file_size), not by actually
    # decompressing gigabytes in a test. Lowers the cap instead of writing
    # a genuinely huge file.
    monkeypatch.setattr(docx_parser, "MAX_DOCX_UNCOMPRESSED_BYTES", 1000)
    bomb = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", "x" * 2000)  # declares file_size=2000 > cap

    with pytest.raises(ValidationFailedError) as exc_info:
        ingest_document(bomb)
    assert "unreasonably large" in exc_info.value.detail


def test_docx_with_suspicious_compression_ratio_is_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(docx_parser, "MAX_DOCX_COMPRESSION_RATIO", 5)
    bomb = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        # Highly repetitive content compresses far past a 5x ratio.
        archive.writestr("word/document.xml", "A" * 100_000)

    with pytest.raises(ValidationFailedError) as exc_info:
        ingest_document(bomb)
    assert "compression ratio" in exc_info.value.detail


def test_docx_within_normal_limits_is_not_rejected():
    # The real benchmark DOCX must not trip either new guard at their
    # real (non-monkeypatched) production thresholds.
    doc = ingest_document(BENCHMARK_DIR / "sample_contract_de.docx")
    assert doc.file_type == "docx"


def test_pdf_exceeding_page_cap_is_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pdf_parser, "MAX_PDF_PAGES", 2)
    huge = tmp_path / "huge.pdf"
    c = canvas.Canvas(str(huge), pagesize=A4)
    for _ in range(3):
        c.drawString(50, 800, "Vertragsgegenstand dieses Vertrages ist die Erbringung.")
        c.showPage()
    c.save()

    with pytest.raises(ValidationFailedError) as exc_info:
        ingest_document(huge)
    assert "more than 2 pages" in exc_info.value.detail
