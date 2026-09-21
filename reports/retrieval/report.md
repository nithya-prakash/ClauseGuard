# Retrieval evaluation report

Generated: 2026-09-20T14:39:42.772882+00:00
Benchmark: data/benchmark/retrieval/queries.json (15 hand-authored queries against the 15-passage legal corpus)
Corpus size: 15 passages

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | NDCG@5 |
|---|---|---|---|---|---|
| dense | 0.8 | 0.9333 | 0.9333 | 0.8651 | 0.8754 |
| bm25 | 0.8 | 0.9333 | 0.9333 | 0.8667 | 0.8841 |
| hybrid_rrf | 0.8 | 0.9333 | 0.9333 | 0.8639 | 0.8754 |
| hybrid_rrf_reranked | 0.8667 | 1.0 | 1.0 | 0.9333 | 0.9508 |

## Limitations

- Corpus has only 15 passages - this benchmark demonstrates the retrieval pipeline (dense/BM25/RRF/reranker) works correctly end-to-end, not that it generalizes to a large real-world legal corpus. Near-perfect recall at this corpus size is expected and not evidence of strong ranking quality at scale.
- Queries were authored knowing which passage they target - not collected from real user behavior.
- hybrid_rrf_reranked reranks only the top-10 RRF candidates (matching what the live pipeline would feed the cross-encoder) - it cannot recover a relevant passage RRF ranked outside that pool, so its recall is bounded by hybrid_rrf's.
