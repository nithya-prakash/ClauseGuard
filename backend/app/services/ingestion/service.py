from pathlib import Path

from app.core.exceptions import ClauseGuardError, UnsupportedFileTypeError, ValidationFailedError
from app.core.logging import get_logger
from app.schemas.document import NormalizedDocument
from app.services.ingestion.docx_parser import parse_docx
from app.services.ingestion.normalize import normalize_document
from app.services.ingestion.pdf_parser import parse_pdf

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

logger = get_logger(__name__)


def ingest_document(path: Path) -> NormalizedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    try:
        parsed = parse_pdf(path) if suffix == ".pdf" else parse_docx(path)
    except ClauseGuardError:
        # e.g. OCRNotImplementedError from parse_pdf - already a clean,
        # user-safe error, must propagate unchanged, not get re-wrapped.
        raise
    except Exception as exc:
        # pdfplumber/pdfminer (corrupt PDF) and python-docx (corrupt DOCX,
        # e.g. PackageNotFoundError) raise their own library-specific
        # exceptions for malformed input - a genuinely untrusted upload, not
        # a server bug. Without this, these fell through to the generic
        # catch-all 500 handler (main.py) - safe (no info leak) but
        # misleading (implies a server bug, not a bad upload). The real
        # exception is logged server-side; the client gets a clean 422 with
        # no internal details (library name, file paths, stack trace).
        logger.warning(
            "document_parse_failed", suffix=suffix, error=str(exc), exc_type=type(exc).__name__
        )
        raise ValidationFailedError(
            "Could not parse the uploaded file - it may be corrupted or not a valid "
            f"{suffix.lstrip('.').upper()} file."
        ) from exc

    return normalize_document(parsed)
