"""Clause segmentation.

Heuristic, regex-based line segmentation (see patterns.py) - not a full
grammar-based parser. It recognizes German numbered/§/Artikel/Ziffer clause
headers and parenthesized sub-clauses at the start of a line, and splits the
document there. Known limitations (documented rather than hidden):

- Nested clauses (e.g. "3" containing "3.1", "3.2") are returned as a FLAT
  list of clauses in document order, not a tree. The `section` label still
  reflects the nesting (e.g. "3.2").
- Bullet lists are deliberately NOT treated as clause boundaries - they stay
  inside the enclosing clause's text, since a bullet is normally a list item
  within a clause rather than a new clause.
- A clause spanning a page break gets page_start != page_end; this is
  computed from character-offset-to-page mapping (see NormalizedDocument),
  not guessed.
- If no clause-start pattern matches anywhere in the document (e.g. a
  contract using an unrecognized numbering convention), segmentation falls
  back to paragraph-based splitting (blank-line-separated blocks) rather
  than arbitrary fixed-size character chunking.
"""

from app.schemas.clause import Clause
from app.schemas.document import NormalizedDocument
from app.services.segmentation.patterns import CLAUSE_START_PATTERNS


def _find_boundaries(full_text: str) -> list[tuple[int, str, str]]:
    """Return [(char_offset, section_label, heading_text), ...] in order."""
    boundaries: list[tuple[int, str, str]] = []
    offset = 0
    for line in full_text.splitlines(keepends=True):
        stripped = line.strip("\n")
        for pattern in CLAUSE_START_PATTERNS:
            match = pattern.match(stripped)
            if match:
                label = match.group(1)
                heading = stripped[match.end() :].strip()
                boundaries.append((offset, label, heading))
                break
        offset += len(line)
    return boundaries


def _paragraph_fallback(document: NormalizedDocument) -> list[Clause]:
    clauses: list[Clause] = []
    text = document.full_text
    position = 0
    cursor = 0
    for block in text.split("\n\n"):
        stripped = block.strip()
        start = text.index(block, cursor) if block else cursor
        end = start + len(block)
        cursor = end
        if not stripped:
            continue
        position += 1
        clauses.append(
            Clause(
                clause_id=f"c{position:03d}",
                text=stripped,
                section=None,
                heading=None,
                page_start=document.page_for_offset(start),
                page_end=document.page_for_offset(max(start, end - 1)),
                position=position,
                char_start=start,
                char_end=end,
            )
        )
    return clauses


def segment_document(document: NormalizedDocument) -> list[Clause]:
    boundaries = _find_boundaries(document.full_text)
    if not boundaries:
        return _paragraph_fallback(document)

    clauses: list[Clause] = []
    text = document.full_text
    for i, (start, label, heading) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        clause_text = text[start:end].strip()
        if not clause_text:
            continue
        clauses.append(
            Clause(
                clause_id=f"c{i + 1:03d}",
                text=clause_text,
                section=label,
                heading=heading or None,
                page_start=document.page_for_offset(start),
                page_end=document.page_for_offset(max(start, end - 1)),
                position=i + 1,
                char_start=start,
                char_end=end,
            )
        )
    return clauses
