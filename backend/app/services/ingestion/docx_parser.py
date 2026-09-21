import zipfile
from pathlib import Path

import docx

from app.core.exceptions import ValidationFailedError
from app.schemas.document import ParsedPage, ParseResult

# Milestone 16 Phase 17: DOCX is a zip archive - MAX_UPLOAD_SIZE_MB (spec
# section 29) only bounds the COMPRESSED upload size, not what it expands
# to. A crafted archive can compress to a few KB while expanding to
# gigabytes ("zip bomb"), exhausting memory before python-docx ever gets to
# parse a single paragraph. Checked from the zip's own central directory
# (cheap - metadata only, doesn't decompress anything) before handing the
# file to python-docx.
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200MB, generous for a real contract
# A legitimate DOCX (already-compressed XML+media) is nowhere near this ratio.
MAX_DOCX_COMPRESSION_RATIO = 100


def _reject_if_decompression_bomb(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            total_uncompressed = sum(info.file_size for info in archive.infolist())
            total_compressed = sum(info.compress_size for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise ValidationFailedError(
            "Could not parse the uploaded file - it may be corrupted or not a valid DOCX file."
        ) from exc

    if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
        raise ValidationFailedError(
            "The uploaded DOCX file expands to an unreasonably large size and was rejected."
        )
    if total_compressed > 0 and total_uncompressed / total_compressed > MAX_DOCX_COMPRESSION_RATIO:
        raise ValidationFailedError(
            "The uploaded DOCX file has a suspicious compression ratio and was rejected."
        )


def parse_docx(path: Path) -> ParseResult:
    """Extract text from a DOCX file.

    DOCX has no fixed pagination - page breaks depend on the rendering
    engine/fonts, not the file format. We deliberately report the whole
    document as a single logical page rather than guessing page boundaries;
    callers must not assume page_start/page_end are meaningful for DOCX
    sources (see NormalizedDocument.pagination_available).
    """
    _reject_if_decompression_bomb(path)
    document = docx.Document(str(path))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)

    return ParseResult(
        filename=path.name,
        file_type="docx",
        pages=[ParsedPage(page_number=1, text=text)],
        likely_scanned=False,
    )
