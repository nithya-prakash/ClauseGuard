"""Evaluate dense, BM25, and hybrid (RRF) retrieval against the manually
curated benchmark in data/benchmark/retrieval/queries.json. Requires Qdrant
running and the corpus indexed (legal_corpus/ingestion/index_corpus.py).

Every number in reports/retrieval/{results.json,report.md} comes from
actually running the three real retrievers against the real Qdrant/BM25
index - nothing is hand-typed. Cross-encoder reranking is evaluated
separately once it exists (Milestone 7); comparing against it here would be
premature.

Usage:
    QDRANT_URL=http://localhost:6339 python eval/retrieval/evaluate_retrieval.py
"""

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.schemas.retrieval import RetrievedPassage  # noqa: E402
from app.services.retrieval import bm25, dense  # noqa: E402
from app.services.retrieval.config import BM25_TOP_K, DENSE_TOP_K  # noqa: E402
from app.services.retrieval.corpus_loader import load_corpus  # noqa: E402
from app.services.retrieval.rrf import index_passages_by_key, reciprocal_rank_fusion  # noqa: E402

BENCHMARK_PATH = ROOT / "data" / "benchmark" / "retrieval" / "queries.json"
REPORT_DIR = ROOT / "reports" / "retrieval"
K_VALUES = (1, 3, 5)


def result_key(r: RetrievedPassage) -> str:
    return f"{r.source}:{r.section}"


def recall_at_k(ranked_keys: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if relevant & set(ranked_keys[:k]) else 0.0


def reciprocal_rank(ranked_keys: list[str], relevant: set[str]) -> float:
    for i, key in enumerate(ranked_keys, start=1):
        if key in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_keys: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(
        1.0 / math.log2(i + 1) for i, key in enumerate(ranked_keys[:k], start=1) if key in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_method(
    method_name: str, per_query_rankings: dict[str, list[str]], queries: list[dict]
) -> dict:
    metrics = {f"recall_at_{k}": [] for k in K_VALUES}
    metrics["mrr"] = []
    metrics["ndcg_at_5"] = []

    for q in queries:
        relevant = {f"{r['source']}:{r['section']}" for r in q["relevant"]}
        ranked_keys = per_query_rankings[q["query_id"]]
        for k in K_VALUES:
            metrics[f"recall_at_{k}"].append(recall_at_k(ranked_keys, relevant, k))
        metrics["mrr"].append(reciprocal_rank(ranked_keys, relevant))
        metrics["ndcg_at_5"].append(ndcg_at_k(ranked_keys, relevant, 5))

    return {
        "method": method_name,
        **{name: round(sum(values) / len(values), 4) for name, values in metrics.items()},
    }


def main() -> None:
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    passages = load_corpus()
    bm25_index = bm25.build_index(passages)
    passages_by_key = index_passages_by_key(passages)

    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    queries = benchmark["queries"]

    dense_rankings, bm25_rankings, hybrid_rankings = {}, {}, {}
    for q in queries:
        dense_results = dense.search(
            client, settings.qdrant_collection, q["query"], top_k=DENSE_TOP_K
        )
        bm25_results = bm25.search(q["query"], passages, bm25_index, top_k=BM25_TOP_K)
        hybrid_results = reciprocal_rank_fusion([dense_results, bm25_results], passages_by_key)

        dense_rankings[q["query_id"]] = [result_key(r) for r in dense_results]
        bm25_rankings[q["query_id"]] = [result_key(r) for r in bm25_results]
        hybrid_rankings[q["query_id"]] = [result_key(r) for r in hybrid_results]

    results = [
        evaluate_method("dense", dense_rankings, queries),
        evaluate_method("bm25", bm25_rankings, queries),
        evaluate_method("hybrid_rrf", hybrid_rankings, queries),
    ]

    output = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "benchmark": (
            "data/benchmark/retrieval/queries.json "
            "(15 hand-authored queries against the 15-passage legal corpus)"
        ),
        "corpus_size": len(passages),
        "results": results,
        "limitations": [
            "Corpus has only 15 passages - this benchmark demonstrates the "
            "retrieval pipeline (dense/BM25/RRF) works correctly end-to-end, "
            "not that it generalizes to a large real-world legal corpus. "
            "Near-perfect recall at this corpus size is expected and not "
            "evidence of strong ranking quality at scale.",
            "Queries were authored knowing which passage they target - not "
            "collected from real user behavior.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Retrieval evaluation report",
        "",
        f"Generated: {output['evaluated_at']}",
        f"Benchmark: {output['benchmark']}",
        f"Corpus size: {output['corpus_size']} passages",
        "",
        "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | NDCG@5 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['method']} | {r['recall_at_1']} | {r['recall_at_3']} | "
            f"{r['recall_at_5']} | {r['mrr']} | {r['ndcg_at_5']} |"
        )
    lines += ["", "## Limitations", ""]
    lines += [f"- {limitation}" for limitation in output["limitations"]]
    (REPORT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
