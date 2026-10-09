"""Cross-reference extraction: which corpus passages cite which others.

Edges are derived mechanically from the passage text (e.g. BGB § 307 cites
"§§ 308 und 309"), never hand-written, and only link passages that exist in
the corpus. Limitation: a "§ N" inside a passage may point to a different
statute that happens to share the number; the regex cannot tell. Edges are
therefore "textually mentions", not a verified legal dependency.
"""
import re

from app.schemas.legal_passage import LegalPassage

# "§ 307", "§§ 308 und 309", "§§ 305, 306 oder 307"; "Artikel 6" / "Art. 6"
_PARAGRAPH_GROUP = re.compile(r"§§?\s*(\d+[a-z]?(?:\s*(?:,|und|oder|bis)\s*\d+[a-z]?)*)")
_ARTICLE = re.compile(r"\bArt(?:ikel|\.)\s*(\d+)")
_NUMBER = re.compile(r"\d+[a-z]?")

_SECTION_FORMAT = {"BGB": "§ {}", "DSGVO": "Art. {}"}


def _key(source: str, number: str) -> str:
    return f"{source}:{_SECTION_FORMAT[source].format(number)}"


def extract_edges(passages: list[LegalPassage]) -> list[tuple[str, str]]:
    """Returns sorted unique (from_key, to_key) pairs, same-source only,
    no self-loops, targets restricted to passages present in the corpus."""
    keys = {f"{p.source}:{p.section}" for p in passages}
    edges: set[tuple[str, str]] = set()
    for p in passages:
        if p.source not in _SECTION_FORMAT:
            continue
        origin = f"{p.source}:{p.section}"
        numbers: list[str] = []
        if p.source == "BGB":
            for group in _PARAGRAPH_GROUP.findall(p.text):
                numbers += _NUMBER.findall(group)
        else:
            numbers += _ARTICLE.findall(p.text)
        for number in numbers:
            target = _key(p.source, number)
            if target in keys and target != origin:
                edges.add((origin, target))
    return sorted(edges)
