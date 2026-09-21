"""Citation verification (spec section 15). For every LLM-claimed finding,
checks in order:
  1. Does the cited section exist at all (in the known legal corpus)?
  2. Was it actually retrieved as evidence for this clause (not just
     somewhere in the corpus)?
  3. Is the finding's own "legal_basis" text internally consistent with its
     "citation" field - i.e. if legal_basis mentions a section number, does
     it match the one actually cited? (Milestone 16 finding: an earlier
     version of this check compared the matched passage's source against
     itself, which is unreachable dead code - the passage is only ever
     found BY filtering on that same source, so it can never mismatch. This
     replaces it with a check that can actually fail: an LLM restating a
     different section in its own explanation than the one it formally
     cited is a real, previously-uncaught inconsistency.)
  4. Does the finding's claimed "evidence" text genuinely appear in that
     passage (a text-overlap heuristic - not a semantic entailment model;
     a deeper faithfulness check needs a live model to test against, see
     reports/reasoning/).

Any failure is reported as CITATION_UNVERIFIED with a specific reason -
never silently accepted.
"""

import re
from difflib import SequenceMatcher

from app.schemas.reasoning import Finding
from app.schemas.retrieval import RetrievedPassage
from app.schemas.verification import CitationCheckResult
from app.services.retrieval.corpus_loader import load_corpus
from app.services.verification.citation_parser import parse_citation

MIN_TEXT_SUPPORT_RATIO = 0.5


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _text_is_supported(claimed_evidence: str, passage_text: str) -> bool:
    claimed = _normalize(claimed_evidence)
    passage = _normalize(passage_text)
    if not claimed:
        return False
    if claimed in passage:
        return True
    return SequenceMatcher(None, claimed, passage).ratio() >= MIN_TEXT_SUPPORT_RATIO


def verify_citation(
    finding: Finding, retrieved_evidence: list[RetrievedPassage]
) -> CitationCheckResult:
    parsed = parse_citation(finding.citation)
    if parsed is None:
        return CitationCheckResult(
            citation=finding.citation,
            status="CITATION_UNVERIFIED",
            reason=f"Could not parse citation format: '{finding.citation}'.",
        )
    source, section = parsed

    corpus = load_corpus()
    exists_in_corpus = any(p.source == source and p.section == section for p in corpus)
    if not exists_in_corpus:
        return CitationCheckResult(
            citation=finding.citation,
            status="CITATION_UNVERIFIED",
            reason=f"{source} {section} is not a known passage in the legal corpus.",
        )

    matching_evidence = next(
        (p for p in retrieved_evidence if p.source == source and p.section == section), None
    )
    if matching_evidence is None:
        return CitationCheckResult(
            citation=finding.citation,
            status="CITATION_UNVERIFIED",
            reason=f"{source} {section} exists in the corpus but was not among the "
            "evidence retrieved for this clause.",
        )

    legal_basis_citation = parse_citation(finding.legal_basis)
    if legal_basis_citation is not None and legal_basis_citation != (source, section):
        return CitationCheckResult(
            citation=finding.citation,
            status="CITATION_UNVERIFIED",
            reason=(
                f"Finding's legal_basis references {legal_basis_citation[0]} "
                f"{legal_basis_citation[1]}, which does not match its own citation "
                f"field ({source} {section})."
            ),
        )

    if not _text_is_supported(finding.evidence, matching_evidence.text):
        return CitationCheckResult(
            citation=finding.citation,
            status="CITATION_UNVERIFIED",
            reason="Claimed evidence text does not sufficiently match the retrieved "
            f"{source} {section} passage text.",
        )

    return CitationCheckResult(citation=finding.citation, status="VERIFIED", reason=None)
