"""Parses a citation string (as an LLM would write it) into the (source,
section) form used by legal_corpus passages, so it can be looked up.
Deliberately narrow - only the two sources actually in the corpus (spec
section 4's constrained scope). An unparseable citation is a real failure
mode, not swallowed silently - callers treat None as CITATION_UNVERIFIED.
"""

import re

_BGB_RE = re.compile(r"§\s*(\d+[a-zA-Z]?)\s*(?:BGB)?", re.IGNORECASE)
_DSGVO_RE = re.compile(r"Art(?:ikel|\.)?\s*(\d+)\s*(?:DSGVO|GDPR)?", re.IGNORECASE)


def parse_citation(citation: str) -> tuple[str, str] | None:
    bgb_match = _BGB_RE.search(citation)
    if bgb_match:
        return "BGB", f"§ {bgb_match.group(1)}"

    dsgvo_match = _DSGVO_RE.search(citation)
    if dsgvo_match:
        return "DSGVO", f"Art. {dsgvo_match.group(1)}"

    return None
