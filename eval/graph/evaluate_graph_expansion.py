"""Does Neo4j cross-reference expansion improve retrieval? (real run, no hand-typed numbers)

Compares, per benchmark query, the reranked top-5 against the same list plus
graph-expanded passages. To be fair about list length (extra items trivially
raise recall), the baseline is ALSO scored at the expanded list's length, using
the next-ranked reranked candidates.

Requires Qdrant (corpus indexed) and Neo4j (scripts/build_graph.py).
    QDRANT_URL=http://localhost:6339 NEO4J_PASSWORD=... \
        python eval/graph/evaluate_graph_expansion.py
"""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from neo4j import GraphDatabase
from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.graph.service import expand_with_graph  # noqa: E402
from app.services.reranking.config import RERANK_CANDIDATE_POOL, RERANK_TOP_K  # noqa: E402
from app.services.reranking.cross_encoder import rerank  # noqa: E402
from app.services.retrieval import bm25, dense  # noqa: E402
from app.services.retrieval.config import BM25_TOP_K, DENSE_TOP_K  # noqa: E402
from app.services.retrieval.corpus_loader import load_corpus  # noqa: E402
from app.services.retrieval.rrf import index_passages_by_key, reciprocal_rank_fusion  # noqa: E402

REPORT_DIR = ROOT / "reports" / "graph"


def key(p) -> str:
    return f"{p.source}:{p.section}"


def main() -> None:
    s = get_settings()
    client = QdrantClient(url=s.qdrant_url)
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    passages = load_corpus()
    index, by_key = bm25.build_index(passages), index_passages_by_key(passages)
    queries = json.loads((ROOT / "data/benchmark/retrieval/queries.json").read_text())["queries"]

    rows = []
    for q in queries:
        relevant = {f"{r['source']}:{r['section']}" for r in q["relevant"]}
        fused = reciprocal_rank_fusion(
            [dense.search(client, s.qdrant_collection, q["query"], top_k=DENSE_TOP_K),
             bm25.search(q["query"], passages, index, top_k=BM25_TOP_K)], by_key)
        ranked = rerank(q["query"], fused[:RERANK_CANDIDATE_POOL])
        top = ranked[:RERANK_TOP_K]
        expanded = expand_with_graph(driver, top)
        n = len(expanded)
        got_top = {key(p) for p in top}
        got_exp = {key(p) for p in expanded}
        got_same_len = {key(p) for p in ranked[:n]}
        rows.append({
            "query_id": q["query_id"], "added": [key(p) for p in expanded[len(top):]],
            "baseline_top5_hit": bool(relevant & got_top),
            "expanded_hit": bool(relevant & got_exp),
            "baseline_same_length_hit": bool(relevant & got_same_len),
            "relevant_found_only_via_graph": sorted((relevant & got_exp) - got_same_len),
        })

    total = len(rows)
    summary = {
        "queries": total,
        "baseline_top5_recall": sum(r["baseline_top5_hit"] for r in rows) / total,
        "expanded_recall": sum(r["expanded_hit"] for r in rows) / total,
        "baseline_same_length_recall": sum(r["baseline_same_length_hit"] for r in rows) / total,
        "queries_where_graph_added_a_relevant_passage": sum(
            bool(r["relevant_found_only_via_graph"]) for r in rows
        ),
        "queries_where_graph_added_anything": sum(bool(r["added"]) for r in rows),
    }
    out = {"evaluated_at": datetime.now(UTC).isoformat(), "summary": summary, "per_query": rows,
           "limitations": [
               "15-passage corpus and 15 hand-authored queries: baseline recall is likely "
               "already at ceiling, so this can show 'no harm' but cannot show gains at scale.",
               "Edges are textual cross-references, not verified legal dependencies."]}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
