"""Evidence sufficiency check (spec section 12): the reliability gate before
a clause is handed to the LLM reasoning stage. If the retrieval pipeline
did not find anything genuinely relevant, reasoning must not proceed - the
clause is reported as INSUFFICIENT_EVIDENCE rather than letting the model
reason from a weak or empty evidence set.

MIN_RERANK_SCORE is empirically calibrated, not an arbitrary constant: the
cross-encoder (backend/app/services/reranking/cross_encoder.py) outputs raw
(unbounded) relevance logits. Manually probing the live corpus with:
  - a genuinely relevant query -> top score 0.955
  - two clearly off-topic queries (bike repair, a cake recipe) -> top
    scores -5.05 and -5.80
  - a query for a clause type the corpus deliberately does NOT cover
    (non-compete - see the corpus gap documented in the README) -> top
    score -3.94
shows a clean separation around 0. Passages scoring below 0 are the corpus
having nothing better than a topically-unrelated guess to offer.
"""

from app.schemas.retrieval import RetrievedPassage
from app.schemas.verification import EvidenceSufficiencyResult

MIN_RERANK_SCORE = 0.0


def check_evidence_sufficiency(
    passages: list[RetrievedPassage], min_score: float = MIN_RERANK_SCORE
) -> EvidenceSufficiencyResult:
    if not passages:
        return EvidenceSufficiencyResult(
            status="INSUFFICIENT_EVIDENCE",
            reason="No evidence was retrieved for this clause.",
            top_score=None,
            evidence=[],
        )

    top_score = passages[0].score
    if top_score < min_score:
        return EvidenceSufficiencyResult(
            status="INSUFFICIENT_EVIDENCE",
            reason=(
                f"Top retrieved passage score ({top_score}) is below the "
                f"sufficiency threshold ({min_score}) - the legal corpus "
                "likely does not cover this clause type."
            ),
            top_score=top_score,
            evidence=passages,
        )

    return EvidenceSufficiencyResult(
        status="SUFFICIENT", reason=None, top_score=top_score, evidence=passages
    )
