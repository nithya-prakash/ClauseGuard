import pytest
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.schemas.retrieval import RetrievedPassage
from app.services.reranking.cross_encoder import rerank
from app.services.reranking.service import retrieve_and_rerank


def _passage(section: str, text: str) -> RetrievedPassage:
    return RetrievedPassage(
        source="TEST",
        section=section,
        title="t",
        text=text,
        source_url="https://example.invalid",
        score=1.0,
        method="hybrid_rrf",
    )


def test_rerank_empty_candidates_returns_empty_list():
    assert rerank("irrelevant query", []) == []


@pytest.mark.integration
def test_rerank_orders_by_relevance_to_query():
    candidates = [
        _passage("§ 1", "Die Miete ist monatlich im Voraus zu entrichten."),
        _passage(
            "§ 2",
            "Der Auftragnehmer haftet nur für Vorsatz und grobe Fahrlässigkeit "
            "und ist im Übrigen von der Haftung freigestellt.",
        ),
    ]
    results = rerank("Haftungsausschluss für leichte Fahrlässigkeit", candidates)
    assert len(results) == 2
    assert results[0].section == "§ 2"
    assert all(r.method == "hybrid_rrf_reranked" for r in results)
    # Sorted descending by relevance score.
    assert results[0].score >= results[1].score


@pytest.mark.integration
def test_retrieve_and_rerank_against_real_corpus():
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)

    results = retrieve_and_rerank(
        client, "Ein Dauerschuldverhältnis kann aus wichtigem Grund gekündigt werden."
    )
    assert 0 < len(results) <= 5
    assert all(r.method == "hybrid_rrf_reranked" for r in results)
    assert results[0].section == "§ 314"
