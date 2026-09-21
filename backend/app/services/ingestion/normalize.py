import re
from collections import Counter

from app.schemas.document import NormalizedDocument, PageOffset, ParseResult

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_BLANK_LINE_RUN = re.compile(r"\n{3,}")

# A line repeated on more than this fraction of pages is treated as a running
# header/footer (e.g. "Seite 3 von 12", a company letterhead line) and
# stripped. Only checked on documents with real pagination and >= 3 pages -
# on shorter documents, a repeated short line is more likely genuine content.
HEADER_FOOTER_REPEAT_THRESHOLD = 0.5
HEADER_FOOTER_MAX_LEN = 120


def _clean_line(line: str) -> str:
    return _WHITESPACE_RUN.sub(" ", line).strip()


def _detect_headers_footers(pages: list[str]) -> set[str]:
    if len(pages) < 3:
        return set()
    counts: Counter[str] = Counter()
    for page_text in pages:
        seen_this_page = {
            _clean_line(line)
            for line in page_text.splitlines()
            if 0 < len(_clean_line(line)) <= HEADER_FOOTER_MAX_LEN
        }
        counts.update(seen_this_page)
    threshold = max(2, int(len(pages) * HEADER_FOOTER_REPEAT_THRESHOLD))
    return {line for line, count in counts.items() if count >= threshold}


def normalize_document(parsed: ParseResult) -> NormalizedDocument:
    page_texts = [p.text for p in parsed.pages]
    boilerplate = _detect_headers_footers(page_texts)

    full_text_parts: list[str] = []
    page_offsets: list[PageOffset] = []
    cursor = 0

    for page in parsed.pages:
        cleaned_lines = [
            _clean_line(line)
            for line in page.text.splitlines()
            if _clean_line(line) not in boilerplate
        ]
        page_text = _BLANK_LINE_RUN.sub("\n\n", "\n".join(cleaned_lines)).strip()
        # Separator between pages so clause-boundary regexes never merge the
        # last line of one page with the first line of the next.
        chunk = page_text + "\n"

        page_offsets.append(
            PageOffset(page_number=page.page_number, start=cursor, end=cursor + len(chunk))
        )
        full_text_parts.append(chunk)
        cursor += len(chunk)

    return NormalizedDocument(
        filename=parsed.filename,
        file_type=parsed.file_type,
        full_text="".join(full_text_parts),
        page_offsets=page_offsets,
        pagination_available=parsed.file_type == "pdf",
    )
