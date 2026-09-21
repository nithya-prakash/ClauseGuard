import pytest
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.schemas.retrieval import RetrievedPassage
from app.services.reranking.service import retrieve_and_rerank
from app.services.verification.evidence_sufficiency import (
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
    result = check_evidence_sufficiency([])
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.top_score is None
    assert "No evidence" in result.reason


def test_top_score_above_threshold_is_sufficient():
    result = check_evidence_sufficiency([_passage(0.95)])
    assert result.status == "SUFFICIENT"
    assert result.reason is None
    assert result.top_score == 0.95


def test_top_score_below_threshold_is_insufficient():
    result = check_evidence_sufficiency([_passage(-3.94)])
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert str(MIN_RERANK_SCORE) in result.reason


def test_top_score_exactly_at_threshold_is_sufficient():
    result = check_evidence_sufficiency([_passage(MIN_RERANK_SCORE)])
    assert result.status == "SUFFICIENT"


@pytest.mark.integration
def test_relevant_query_against_real_corpus_is_sufficient():
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    results = retrieve_and_rerank(
        client, "Der Verkäufer haftet nur für Vorsatz und grobe Fahrlässigkeit."
    )
    outcome = check_evidence_sufficiency(results)
    assert outcome.status == "SUFFICIENT"


@pytest.mark.integration
def test_off_topic_query_against_real_corpus_is_insufficient():
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    results = retrieve_and_rerank(client, "Wie repariere ich die Kette an meinem Fahrrad?")
    outcome = check_evidence_sufficiency(results)
    assert outcome.status == "INSUFFICIENT_EVIDENCE"
