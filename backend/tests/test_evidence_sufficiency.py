import pytest
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.schemas.retrieval import RetrievedPassage
from app.services.reranking.service import retrieve_and_rerank
from app.services.verification.evidence_sufficiency import (
    LENGTH_PENALTY_ALPHA,
    MIN_RERANK_SCORE,
    check_evidence_sufficiency,
)


def _passage(score: float) -> RetrievedPassage:
    return RetrievedPassage(
        source="BGB",
        section="§ 276",
        title="t",
        text="x",
        source_url="https://example.invalid",
        score=score,
        method="hybrid_rrf_reranked",
    )


def test_no_passages_is_insufficient():
    result = check_evidence_sufficiency([], clause_length=100)
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.top_score is None
    assert result.adjusted_score is None
    assert "No evidence" in result.reason


def test_top_score_above_threshold_at_zero_length_is_sufficient():
    # clause_length=0 disables the length penalty (log(1)=0) - isolates the
    # raw threshold behavior from the length adjustment.
    result = check_evidence_sufficiency([_passage(MIN_RERANK_SCORE + 0.5)], clause_length=0)
    assert result.status == "SUFFICIENT"
    assert result.reason is None
    assert result.adjusted_score == pytest.approx(MIN_RERANK_SCORE + 0.5)


def test_top_score_below_threshold_at_zero_length_is_insufficient():
    result = check_evidence_sufficiency([_passage(MIN_RERANK_SCORE - 0.5)], clause_length=0)
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert str(MIN_RERANK_SCORE) in result.reason


def test_top_score_exactly_at_threshold_at_zero_length_is_sufficient():
    result = check_evidence_sufficiency([_passage(MIN_RERANK_SCORE)], clause_length=0)
    assert result.status == "SUFFICIENT"


def test_longer_clause_needs_a_higher_raw_score_to_pass():
    """The core Milestone 16 finding: the same raw score that passes for a
    short clause must NOT automatically pass for a much longer one, because
    the length penalty subtracts more from it (logarithmically)."""
    score = MIN_RERANK_SCORE + 5.0
    short = check_evidence_sufficiency([_passage(score)], clause_length=10)
    long = check_evidence_sufficiency([_passage(score)], clause_length=5000)
    assert short.status == "SUFFICIENT"
    assert long.status == "INSUFFICIENT_EVIDENCE"
    assert long.adjusted_score < short.adjusted_score


# ---------------------------------------------------------------------------
# Phase 10 regression tests (Milestone 16) - the 8 cases the spec calls for,
# using real corpus-shaped scores (not invented numbers) drawn from the
# actual calibration run in reports/evidence_sufficiency/results.json. Every
# expected outcome below was recomputed against the FINAL, frozen rule
# (logarithmic length penalty, threshold=-9.3528, alpha=2.0) - not assumed.
# ---------------------------------------------------------------------------
def test_short_supported_clause_is_sufficient():
    # liability_limitation_short: real top_score 1.695, length 66 chars.
    result = check_evidence_sufficiency([_passage(1.695)], clause_length=66)
    assert result.status == "SUFFICIENT"


def test_long_supported_clause_is_sufficient():
    # general_terms_severability_long: real top_score 8.325, length 588 chars.
    result = check_evidence_sufficiency([_passage(8.325)], clause_length=588)
    assert result.status == "SUFFICIENT"


def test_short_unsupported_clause_is_insufficient():
    # confidentiality_short: real top_score -0.491, length 173 chars.
    result = check_evidence_sufficiency([_passage(-0.491)], clause_length=173)
    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_long_unsupported_clause_is_insufficient():
    """general_terms_scope_long: a long clause about a genuinely uncovered
    topic (subject-matter/scope definition), real top_score 3.248, length
    711 chars - this was a false positive under the ORIGINAL threshold
    (0.0) and is one of the 7 real cases the Milestone 16 recalibration
    fixed (see reports/evidence_sufficiency/results.json's
    fixed_by_calibration list)."""
    result = check_evidence_sufficiency([_passage(3.248)], clause_length=711)
    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_known_remaining_false_positive_is_documented_not_hidden():
    """confidentiality_long: real top_score 4.765, length 585 chars - a
    genuinely uncovered topic (confidentiality) that the Milestone 16
    recalibration did NOT manage to fix (see results.json's
    wrong_under_both list). This test asserts the system's actual current
    (imperfect) behavior and documents WHY, rather than silently passing or
    hiding the limitation: at this combination of score and length, the
    calibrated rule still says SUFFICIENT. This is exactly the kind of
    disclosed, unresolved failure the project's anti-fabrication policy
    requires surfacing rather than glossing over - see README's Limitations
    section and reports/evidence_sufficiency/report.md's error analysis."""
    result = check_evidence_sufficiency([_passage(4.765)], clause_length=585)
    assert result.status == "SUFFICIENT"  # known false positive, not a target behavior


def test_partially_supported_short_clause_is_sufficient():
    # payment_deadline_short: real top_score -0.399, length 81 chars - a
    # PARTIAL-coverage example (BGB Sec. 308 Nr.1a is relevant but generic).
    # This was ALSO one of the 7 real fixes from recalibration.
    result = check_evidence_sufficiency([_passage(-0.399)], clause_length=81)
    assert result.status == "SUFFICIENT"


def test_ambiguous_clause_does_not_crash_and_returns_a_defined_status():
    # data_processing_vague: real top_score 1.716, length 110 chars.
    result = check_evidence_sufficiency([_passage(1.716)], clause_length=110)
    assert result.status in ("SUFFICIENT", "INSUFFICIENT_EVIDENCE")


def test_high_lexical_similarity_wrong_legal_meaning_is_insufficient():
    """non_compete_lexical_trap: a clause about post-contractual competition
    restriction (genuinely uncovered) that heavily reuses 'Kuendigung'/
    'Vertrag' vocabulary, real top_score 1.585, length 266 chars - the
    un-calibrated threshold (0.0) said SUFFICIENT here purely from lexical
    overlap with BGB Sec. 314's termination text. This was fixed by
    recalibration."""
    result = check_evidence_sufficiency([_passage(1.585)], clause_length=266)
    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_no_retrieved_evidence_is_insufficient_regardless_of_clause_length():
    result = check_evidence_sufficiency([], clause_length=5000)
    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_length_penalty_constant_is_positive_and_nonzero():
    """Guards against a future edit accidentally zeroing out the
    length-penalty fix this milestone added."""
    assert LENGTH_PENALTY_ALPHA > 0


@pytest.mark.integration
def test_relevant_query_against_real_corpus_is_sufficient():
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    query = "Der Verkäufer haftet nur für Vorsatz und grobe Fahrlässigkeit."
    results = retrieve_and_rerank(client, query)
    outcome = check_evidence_sufficiency(results, clause_length=len(query))
    assert outcome.status == "SUFFICIENT"


@pytest.mark.integration
def test_off_topic_query_against_real_corpus_is_insufficient():
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    query = "Wie repariere ich die Kette an meinem Fahrrad?"
    results = retrieve_and_rerank(client, query)
    outcome = check_evidence_sufficiency(results, clause_length=len(query))
    assert outcome.status == "INSUFFICIENT_EVIDENCE"
