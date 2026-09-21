"""OCR fallback architecture for scanned PDFs.

Not implemented. This module exists so the ingestion pipeline has a clean
seam to plug a real OCR backend (e.g. Tesseract, a hosted OCR API) into
later, without pretending it already works. `parse_pdf` in pdf_parser.py
calls `get_ocr_provider().extract_text(...)` only when a PDF is flagged
`likely_scanned`; the default provider raises OCRNotImplementedError with a
clear message instead of returning fabricated or empty text.

To implement: satisfy the OCRProvider protocol (e.g. wrap `pytesseract` +
`pdf2image`, or a cloud OCR API) and swap it in via get_ocr_provider().
"""

from pathlib import Path
from typing import Protocol

from app.core.exceptions import OCRNotImplementedError
from app.schemas.document import ParsedPage


class OCRProvider(Protocol):
    def extract_text(self, pdf_path: Path) -> list[ParsedPage]: ...


class UnimplementedOCRProvider:
    def extract_text(self, pdf_path: Path) -> list[ParsedPage]:
        raise OCRNotImplementedError(
            "This PDF appears to be scanned/image-only (very little extractable "
            "text). OCR is not implemented yet - the document cannot be processed. "
            "See services/ingestion/ocr.py for the integration seam."
        )


def get_ocr_provider() -> OCRProvider:
    return UnimplementedOCRProvider()
