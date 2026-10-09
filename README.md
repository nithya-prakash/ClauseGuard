# ClauseGuard

First-pass risk screening for German contracts: clause segmentation, LoRA classification, hybrid legal retrieval with an evidence gate, and citation-checked LLM reasoning. **Not legal advice.**

[![CI](https://github.com/nithya-prakash/ClauseGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/nithya-prakash/ClauseGuard/actions/workflows/ci.yml) ![Python 3.12](https://img.shields.io/badge/python-3.12-blue) ![License MIT](https://img.shields.io/badge/license-MIT-green)

![ClauseGuard demo](docs/demo.gif)

*Upload, analysis and the PDF report. Neo4j expansion is not shown (it is off by default and showed no gain).*

![Review API and MCP server](docs/demo_review_mcp.gif)

*Human review API and MCP tools, run against a local stack without an API key, so every clause is flagged for review.*

> ClauseGuard gives an AI-assisted screening signal. It does not decide whether a contract is legally valid. Consult a qualified lawyer.

## Results

Every number comes from a script in `eval/` that writes to `reports/`. All benchmarks are small and hand-authored by the same person who built the system, so read them as "the pipeline works", not as accuracy claims.

| Component | Result | Benchmark |
|---|---|---|
| Segmentation | 10/10 clauses on the original contract; exact on **4 of 5** contracts (a wrapped line starting "50 Prozent" is read as a heading) | 5 synthetic contracts |
| Classification, LoRA vs TF-IDF baseline | accuracy **0.56** [0.43, 0.67] vs **0.62** [0.50, 0.73]; macro F1 0.55 vs 0.63 | 63 clauses, 5 contracts |
| Classification, held-out split of the training data | macro F1 0.59 vs 0.547 | 20 examples |
| Retrieval, dense + BM25 + RRF + reranker | Recall@1 0.87, Recall@5 **1.00**, NDCG@5 0.95 | 15 queries over a 15-passage corpus |
| End-to-end classification | 0.80 accuracy | the same 10-clause contract |
| Evidence-sufficiency gate | accuracy 0.30 → 0.60 → **0.70** across two recalibrations (10-clause benchmark); **0.79** [0.68, 0.88] on the 63-clause set | 54-example calibration set; 63 clauses |
| Graph expansion (Neo4j) | **no measured gain**: Recall@5 1.00 with and without it | 15 queries |
| LLM reasoning and citation verification | **not measured** | needs an Anthropic key |
| Tests | 138 collected; 134 pass (unit + integration, with Neo4j), 1 live-LLM test skipped, 3 live-website tests excluded; ruff and mypy clean | |

On the larger 63-clause benchmark the LoRA classifier does **not** beat the TF-IDF baseline (intervals overlap; 10 clauses resemble training clauses, and excluding them gives 0.53 vs 0.57), so the earlier LoRA gain on 20 examples did not hold up. The pipeline still uses LoRA by default. Retrieval is at ceiling because the corpus has only 15 passages, so the reranker's +0.07 Recall@1 is a weak signal. Details and caveats are in each report under `reports/`.

## Quickstart

```bash
cp .env.example .env
docker compose up -d --build
QDRANT_URL=http://localhost:6339 python legal_corpus/ingestion/index_corpus.py
open http://localhost:3005
```

No API key is needed. Without `ANTHROPIC_API_KEY` the reasoning stage returns `NOT_CONFIGURED` instead of inventing output.

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | enables LLM reasoning (never run live here) |
| `DATABASE_URL`, `QDRANT_URL`, `REDIS_URL`, `CELERY_*` | service endpoints; `.env.example` uses docker-network names |
| `GRAPH_EXPANSION_ENABLED` | optional Neo4j expansion, default `false` |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Neo4j connection (compose default password `clauseguard-dev`) |
| `CORS_ALLOWED_ORIGINS` | allowed frontend origins |

## How it works

```mermaid
flowchart TD
    A[PDF/DOCX] --> B[Segment into clauses]
    B --> C[LoRA DistilBERT: 10 classes]
    B --> D[Dense + BM25 + RRF + cross-encoder rerank]
    D -.optional.-> N[Neo4j: add cited passages]
    D --> E{Evidence sufficient?}
    E -- no --> F[INSUFFICIENT_EVIDENCE, no LLM call]
    E -- yes --> G[Claude tool-use reasoning]
    G --> H[Citation verification]
    C --> I[Per-clause result]
    F --> I
    H --> I
    I --> J[Web UI, PDF report, Postgres]
```

Stack: FastAPI, Postgres, Qdrant, Redis/Celery, Next.js 16, `distilbert-base-multilingual-cased` + PEFT LoRA, `multilingual-e5-small`, `rank_bm25`, reportlab.

## Usage

```bash
curl -X POST localhost:8004/documents -F "file=@contract.pdf;type=application/pdf"
curl -X POST localhost:8004/documents/{id}/analyze
curl localhost:8004/documents/{id}/report -o report.pdf
```

Review flagged clauses (MEDIUM/HIGH risk, insufficient evidence, unverified citation, low confidence, pipeline error):

```bash
curl localhost:8004/documents/{id}/review
curl -X PUT localhost:8004/documents/{id}/review -H 'content-type: application/json' \
  -d '{"decisions": {"c001": {"decision": "ESCALATE", "note": "needs a lawyer"}}}'
```

Decisions are CONFIRM, DISMISS or ESCALATE and never change the AI risk level; clauses without a decision stay `UNREVIEWED`. Also available: an optional async path through Celery, and a read-only MCP server (`cd backend && python -m app.mcp_server`) with tools `get_scope`, `search_legal_corpus`, `get_passage`, `related_passages`, tested over stdio.

## Evaluation method

Each `eval/<component>/` script runs the real pipeline and writes a report plus raw JSON to `reports/`. Splits are deterministic (positional, no seed). Reports mark anything unrun as `NOT_MEASURED` rather than estimating it. The evidence gate was recalibrated twice on held-out splits; a candidate that looked better on one split but had an identical confusion matrix on the full sample was discarded ([reports/evidence_sufficiency/](reports/evidence_sufficiency/)).

```bash
python eval/segmentation/evaluate_segmentation.py
QDRANT_URL=http://localhost:6339 python eval/benchmark/evaluate_benchmark.py   # 5 contracts, 63 clauses
python eval/classification/evaluate_lora.py
QDRANT_URL=http://localhost:6339 python eval/retrieval/evaluate_retrieval.py
QDRANT_URL=http://localhost:6339 python eval/end_to_end/evaluate_end_to_end.py
NEO4J_PASSWORD=clauseguard-dev QDRANT_URL=http://localhost:6339 python eval/graph/evaluate_graph_expansion.py
```

## Feature status

| Feature | Status |
|---|---|
| LoRA classifier (encoder, classification head) | implemented, trained, evaluated |
| Hybrid retrieval, reranker, evidence gate, citation verification | implemented and tested |
| Neo4j graph expansion | implemented, tested against a real Neo4j 5.26; **no measured benefit**, off by default |
| MCP server | implemented, tested over stdio |
| Human-in-the-loop review (LangGraph `interrupt`) | implemented, tested, exposed as `GET/PUT /documents/{id}/review`; decisions persist in Postgres; **no UI yet** |
| LLM reasoning | implemented; **never run against the live Anthropic API** |
| QLoRA, SFT of a generative model, quantization | **not implemented** |
| Synthetic data generation with an LLM | **not implemented**; the 120 training clauses and all benchmarks are hand-written |

## Limitations

- The 63-clause benchmark (4 contracts written for it plus the original) is small and authored and labelled by the same person who built the system. There is no independent test set.
- Known bug: the segmenter splits a clause when a wrapped line starts with a number (`eval/benchmark`, `kaufvertrag_maschine`). Not fixed.
- Live Anthropic inference is untested, so reasoning quality, schema validity and citation accuracy under a real model are unknown.
- The evidence gate is 0.70 accurate and the adopted fix added two false negatives on clauses covered by several topics.
- The legal corpus is 15 BGB/DSGVO passages with gaps (no dedicated payment or confidentiality provisions). Graph edges are textual cross-references, not verified legal dependencies.
- The frontend still calls the synchronous endpoint; rate limiting is per process; no Playwright suite; Docker Compose only, no hosted demo.
- Frontend dev-tooling advisories remain (Tailwind 3, `eslint-config-next`) and need major upgrades. Runtime dependencies audit clean.

## Repository layout and checks

```
backend/    FastAPI app, Alembic migrations, tests (graph/, review/, mcp_server.py)
frontend/   Next.js UI (Vitest tests)
eval/       evaluation scripts per component        reports/   their outputs
data/benchmark/  hand-written contracts and labels (contracts/ holds the 4 new ones)
training/   LoRA scripts, config, adapter           legal_corpus/  passages and indexing
```

```bash
pip install -e ".[dev]" && ruff check . && mypy backend/app
pytest -m "not integration"                      # unit tier, no services
# integration tier needs the compose stack; from the host, point at the mapped ports:
DATABASE_URL=postgresql+psycopg://clauseguard:clauseguard@localhost:5436/clauseguard \
QDRANT_URL=http://localhost:6339 REDIS_URL=redis://localhost:6383/0 \
CELERY_BROKER_URL=redis://localhost:6383/0 CELERY_RESULT_BACKEND=redis://localhost:6383/1 \
NEO4J_PASSWORD=clauseguard-dev pytest -m "integration and not external_flaky"
```

Integration tests skip quickly when Postgres or Qdrant is unreachable (and fail when `CI` is set). CI runs lint, mypy, unit and integration tests, frontend lint/test/build, dependency audits and Docker builds.

## License

MIT, see [LICENSE](LICENSE).
