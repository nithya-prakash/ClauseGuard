from typing import Literal

from pydantic import BaseModel


class ParsedPage(BaseModel):
    """One page of raw extracted text, before normalization."""

    page_number: int
    text: str


class ParseResult(BaseModel):
    filename: str
    file_type: Literal["pdf", "docx"]
    pages: list[ParsedPage]
    # Heuristic flag: text density is too low for this to be a real digital
    # document (e.g. a scanned/image-only PDF). See services/ingestion/ocr.py.
    likely_scanned: bool


class PageOffset(BaseModel):
    """Maps a character range in NormalizedDocument.full_text to a page."""

    page_number: int
    start: int
    end: int


class NormalizedDocument(BaseModel):
    filename: str
    file_type: Literal["pdf", "docx"]
    full_text: str
    page_offsets: list[PageOffset]
    # DOCX has no fixed pagination (it reflows) - all text is reported as a
    # single logical page. This is a documented limitation, not a bug.
    pagination_available: bool

    def page_for_offset(self, offset: int) -> int | None:
        for po in self.page_offsets:
            if po.start <= offset < po.end:
                return po.page_number
        return self.page_offsets[-1].page_number if self.page_offsets else None
