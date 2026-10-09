from unittest.mock import MagicMock

from app.schemas.legal_passage import LegalPassage
from app.schemas.retrieval import RetrievedPassage
from app.services.graph.references import extract_edges
from app.services.graph.service import expand_with_graph
from app.services.graph.store import NEIGHBOURS, GraphStore
from app.services.retrieval.corpus_loader import load_corpus


def _p(source, section, text="") -> LegalPassage:
    return LegalPassage(
        source=source, section=section, title="t", text=text, jurisdiction="x", domain="d",
        source_url="u", effective_date=None, retrieved_at="now",
    )


def test_extract_edges_handles_groups_and_filters():
    passages = [
        _p("BGB", "§ 307", "siehe §§ 308 und 309 sowie § 999 und § 307"),
        _p("BGB", "§ 308"), _p("BGB", "§ 309"),
        _p("DSGVO", "Art. 28", "nach Artikel 6 und Artikel 82"), _p("DSGVO", "Art. 6"),
    ]
    assert extract_edges(passages) == [
        ("BGB:§ 307", "BGB:§ 308"),
        ("BGB:§ 307", "BGB:§ 309"),
        ("DSGVO:Art. 28", "DSGVO:Art. 6"),
    ]


def test_extract_edges_on_real_corpus_only_targets_existing_passages():
    corpus = load_corpus()
    keys = {f"{p.source}:{p.section}" for p in corpus}
    edges = extract_edges(corpus)
    assert edges and all(a in keys and b in keys and a != b for a, b in edges)
    assert ("BGB:§ 307", "BGB:§ 308") in edges


def _driver(rows):
    driver, session = MagicMock(), MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.run.return_value = rows
    return driver, session


def test_upsert_corpus_runs_node_and_edge_statements():
    driver, session = _driver([])
    GraphStore(driver).upsert_corpus(
        [_p("BGB", "§ 307"), _p("BGB", "§ 308")], [("BGB:§ 307", "BGB:§ 308")], "v1"
    )
    calls = session.run.call_args_list
    assert len(calls) == 3
    assert calls[2].kwargs == {"from_key": "BGB:§ 307", "to_key": "BGB:§ 308"}


def test_neighbours_passes_seed_keys_and_limit():
    driver, session = _driver([{"key": "BGB:§ 308"}])
    assert GraphStore(driver).neighbours(["BGB:§ 307"], 2) == ["BGB:§ 308"]
    assert session.run.call_args.args[0] == NEIGHBOURS
    assert session.run.call_args.kwargs == {"keys": ["BGB:§ 307"], "limit": 2}


def _seed(section="§ 307", score=0.8):
    return RetrievedPassage(
        source="BGB", section=section, title="t", text="x", source_url="u",
        score=score, method="hybrid_rrf",
    )


def test_expand_adds_real_corpus_passages_with_lower_score():
    driver, _ = _driver([{"key": "BGB:§ 308"}, {"key": "BGB:§ 000"}])  # second is unknown
    out = expand_with_graph(driver, [_seed()])
    assert [p.section for p in out] == ["§ 307", "§ 308"]
    assert out[1].method == "graph_expanded" and out[1].score == 0.4
    assert out[1].source_url.startswith("https://")  # real provenance from corpus


def test_expand_fails_open_on_driver_error():
    driver = MagicMock()
    driver.session.side_effect = RuntimeError("neo4j down")
    seeds = [_seed()]
    assert expand_with_graph(driver, seeds) == seeds



def _live_driver():
    import pytest
    from neo4j import GraphDatabase

    from app.core.config import get_settings

    s = get_settings()
    try:
        driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
        driver.verify_connectivity()
    except Exception:  # noqa: BLE001
        pytest.skip("Neo4j not reachable (docker compose up -d neo4j)")
    return driver


def test_live_neo4j_roundtrip_matches_corpus_edges():
    from app.services.graph.references import extract_edges

    driver = _live_driver()
    corpus = load_corpus()
    GraphStore(driver).upsert_corpus(corpus, extract_edges(corpus), "test")
    assert "BGB:§ 308" in GraphStore(driver).neighbours(["BGB:§ 307"], 10)
