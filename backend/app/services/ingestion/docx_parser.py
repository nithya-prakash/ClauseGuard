from pathlib import Path

import docx

from app.schemas.document import ParsedPage, ParseResult


def parse_docx(path: Path) -> ParseResult:
    """Extract text from a DOCX file.

    DOCX has no fixed pagination - page breaks depend on the rendering
    engine/fonts, not the file format. We deliberately report the whole
    document as a single logical page rather than guessing page boundaries;
    callers must not assume page_start/page_end are meaningful for DOCX
    sources (see NormalizedDocument.pagination_available).
    """
    document = docx.Document(str(path))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)

    return ParseResult(
        filename=path.name,
        file_type="docx",
        pages=[ParsedPage(page_number=1, text=text)],
        likely_scanned=False,
    )
