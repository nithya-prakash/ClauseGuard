import pytest
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.schemas.legal_passage import LegalPassage
from app.schemas.retrieval import RetrievedPassage
from app.services.retrieval import bm25, dense
from app.services.retrieval.corpus_loader import load_corpus, passage_key
from app.services.retrieval.rrf import index_passages_by_key, reciprocal_rank_fusion
from app.services.retrieval.service import hybrid_search


def _passage(source: str, section: str, text: str) -> LegalPassage:
    return LegalPassage(
        source=source,
        section=section,
        title="Test title",
        text=text,
        jurisdiction="Germany",
        domain="contract_law",
        source_url="https://example.invalid",
        effective_date=None,
        retrieved_at="2026-01-01T00:00:00+00:00",
    )


def test_tokenize_lowercases_and_strips_punctuation():
    tokens = bm25.tokenize("Haftung für Vorsatz, grobe Fahrlässigkeit!")
    assert tokens == ["haftung", "für", "vorsatz", "grobe", "fahrlässigkeit"]


def test_bm25_search_ranks_lexically_matching_passage_first():
    # 3 passages, not 2: with only 2 documents, rank_bm25's classic Okapi
    # IDF formula (log(N-freq+0.5) - log(freq+0.5)) is exactly 0 for a term
    # in exactly 1 of 2 docs, giving every passage a score of 0 - not a bug
    # in the search code, just an edge case of BM25 IDF at tiny N.
    passages = [
        _passage("TEST", "§ 1", "Der Auftragnehmer haftet für Vorsatz und grobe Fahrlässigkeit."),
        _passage("TEST", "§ 2", "Die Miete ist monatlich im Voraus zu entrichten."),
        _passage("TEST", "§ 3", "Änderungen bedürfen der Textform."),
    ]
    index = bm25.build_index(passages)
    results = bm25.search("Haftung Vorsatz Fahrlässigkeit", passages, index, top_k=5)
    assert results[0].section == "§ 1"


def test_bm25_search_excludes_zero_score_passages():
    passages = [_passage("TEST", "§ 1", "Ganz anderer Text ohne Bezug.")]
    index = bm25.build_index(passages)
    results = bm25.search("völlig unrelated query terms", passages, index, top_k=5)
    assert results == []


def test_reciprocal_rank_fusion_combines_two_rankings():
    passages = [
        _passage("TEST", "§ 1", "a"),
        _passage("TEST", "§ 2", "b"),
        _passage("TEST", "§ 3", "c"),
    ]
    by_key = index_passages_by_key(passages)

    def make(method: str, sections: list[str]) -> list[RetrievedPassage]:
        return [
            RetrievedPassage(
                source="TEST",
                section=s,
                title="t",
                text="x",
                source_url="https://example.invalid",
                score=1.0,
                method=method,  # type: ignore[arg-type]
            )
            for s in sections
        ]

    ranking_a = make("dense", ["§ 1", "§ 2", "§ 3"])
    ranking_b = make("bm25", ["§ 2", "§ 1", "§ 3"])

    fused = reciprocal_rank_fusion([ranking_a, ranking_b], by_key)

    # § 1 and § 2 are each ranked #1 in one list and #2 in the other, so they
    # should tie for the top of the fused ranking, ahead of § 3 (always last).
    assert {fused[0].section, fused[1].section} == {"§ 1", "§ 2"}
    assert fused[2].section == "§ 3"


def test_passage_key_format():
    p = _passage("BGB", "§ 307", "text")
    assert passage_key(p) == "BGB:§ 307"


@pytest.mark.integration
def test_dense_search_against_real_qdrant_and_corpus():
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    results = dense.search(
        client, settings.qdrant_collection, "Haftung für Vorsatz und grobe Fahrlässigkeit", top_k=3
    )
    assert len(results) > 0
    assert all(r.method == "dense" for r in results)


@pytest.mark.integration
def test_hybrid_search_against_real_corpus():
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    corpus = load_corpus()
    assert len(corpus) == 15

    results = hybrid_search(client, "Voraussetzungen für die wirksame Einbeziehung von AGB")
    assert len(results) > 0
    assert all(r.method == "hybrid_rrf" for r in results)
