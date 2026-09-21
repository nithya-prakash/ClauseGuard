"""Evidence sufficiency check (spec section 12): the reliability gate before
a clause is handed to the LLM reasoning stage. If the retrieval pipeline
did not find anything genuinely relevant, reasoning must not proceed - the
clause is reported as INSUFFICIENT_EVIDENCE rather than letting the model
reason from a weak or empty evidence set.

Milestone 16 recalibration (see reports/evidence_sufficiency/ for the full
methodology - dataset, split, and every candidate tried, not just the
winner): the original MIN_RERANK_SCORE=0.0 threshold was calibrated on 4
short standalone queries and measured 0.30 accuracy on the real 10-clause
end-to-end benchmark (reports/end_to_end/results.json, pre-recalibration).

A 40-example calibration dataset built from real full-length clause text
(data/benchmark/evidence_sufficiency/dataset.json) showed the cross-encoder's
raw top score is measurably inflated by clause length regardless of true
relevance: within every family of same-topic, genuinely-uncovered clauses,
SHORT variants scored correctly negative while MEDIUM/LONG variants of the
exact same legal content scored increasingly positive (e.g.
confidentiality_short -0.49 vs confidentiality_long +4.77 - same uncovered
topic, same raw threshold would call one right and one wrong).

A LOGARITHMIC length penalty (adjusted_score = top_score - alpha *
log(clause_length)) was selected over a linear one after the linear
candidate, which looked like an improvement on a small held-out split, was
shown to have an IDENTICAL confusion matrix to the uncalibrated baseline on
the full 35-example pooled sample - it only relocated which examples were
wrong, it did not reduce error. That check is why this file's methodology
notes are worth reading before changing these constants again: it is easy
to "improve" a small held-out split without improving anything real.

The log penalty does show a genuine full-population improvement (accuracy
0.714->0.886, false-positive rate 0.538->0.077, no recall cost) and a real
held-out-test improvement scored ONCE after the rule was frozen on
calibration+validation (accuracy 0.70->0.90, false-positive rate
0.75->0.25, recall unchanged at 1.0).

This is NOT claimed to be a solved problem: N=35 conclusive calibration
examples is small, and this remains an important reliability caveat (see
README's Limitations section) - it is a real, measured improvement over the
uncalibrated baseline on the same data, not a guarantee for arbitrary
future contracts.
"""

import math

from app.schemas.retrieval import RetrievedPassage
from app.schemas.verification import EvidenceSufficiencyResult

MIN_RERANK_SCORE = -9.3528
LENGTH_PENALTY_ALPHA = 2.0


def check_evidence_sufficiency(
    passages: list[RetrievedPassage],
    clause_length: int,
    min_score: float = MIN_RERANK_SCORE,
    length_penalty: float = LENGTH_PENALTY_ALPHA,
) -> EvidenceSufficiencyResult:
    """clause_length is the character length of the clause text the passages
    were retrieved for - required (not defaulted) so a caller cannot
    silently bypass the length penalty by omitting it. Pass clause_length=0
    to disable the penalty (adjusted_score becomes the raw top_score)."""
    if not passages:
        return EvidenceSufficiencyResult(
            status="INSUFFICIENT_EVIDENCE",
            reason="No evidence was retrieved for this clause.",
            top_score=None,
            adjusted_score=None,
            evidence=[],
        )

    top_score = passages[0].score
    adjusted = top_score - length_penalty * math.log(max(clause_length, 1))
    if adjusted < min_score:
        return EvidenceSufficiencyResult(
            status="INSUFFICIENT_EVIDENCE",
            reason=(
                f"Top retrieved passage score ({top_score}), length-adjusted to "
                f"{adjusted:.3f} for a {clause_length}-character clause, is below "
                f"the sufficiency threshold ({min_score}) - the legal corpus likely "
                "does not cover this clause."
            ),
            top_score=top_score,
            adjusted_score=adjusted,
            evidence=passages,
        )

    return EvidenceSufficiencyResult(
        status="SUFFICIENT",
        reason=None,
        top_score=top_score,
        adjusted_score=adjusted,
        evidence=passages,
    )
