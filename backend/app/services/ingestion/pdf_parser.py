from pathlib import Path

import pdfplumber

from app.schemas.document import ParsedPage, ParseResult
from app.services.ingestion.ocr import get_ocr_provider

# Below this average character count per page, a PDF is treated as
# likely-scanned (image-only) rather than a real digital document. This is a
# heuristic, not a certainty - chosen conservatively so a short but genuine
# digital page (e.g. a signature page) isn't misflagged on its own; it's the
# *average* across the document that's checked.
MIN_AVG_CHARS_PER_PAGE = 40


def parse_pdf(path: Path) -> ParseResult:
    pages: list[ParsedPage] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(ParsedPage(page_number=i, text=text))

    total_chars = sum(len(p.text) for p in pages)
    avg_chars_per_page = total_chars / len(pages) if pages else 0
    likely_scanned = avg_chars_per_page < MIN_AVG_CHARS_PER_PAGE

    if likely_scanned:
        # Raises OCRNotImplementedError today; this is the seam a real OCR
        # backend plugs into later (see services/ingestion/ocr.py).
        pages = get_ocr_provider().extract_text(path)

    return ParseResult(
        filename=path.name,
        file_type="pdf",
        pages=pages,
        likely_scanned=likely_scanned,
    )
