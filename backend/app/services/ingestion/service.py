from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError
from app.schemas.document import NormalizedDocument
from app.services.ingestion.docx_parser import parse_docx
from app.services.ingestion.normalize import normalize_document
from app.services.ingestion.pdf_parser import parse_pdf

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def ingest_document(path: Path) -> NormalizedDocument:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        parsed = parse_pdf(path)
    elif suffix == ".docx":
        parsed = parse_docx(path)
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    return normalize_document(parsed)
