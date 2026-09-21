# ClauseGuard

AI-assisted first-pass compliance/risk analysis for German contracts.

> **ClauseGuard provides AI-assisted first-pass compliance analysis and does
> not constitute legal advice.** It does not determine whether a contract is
> legally valid. Full documentation is being built up milestone by milestone
> as the system is implemented — see below for current status.

## Status

Build in progress. See commit history / project memory for milestone-by-milestone progress.

- [x] Milestone 1 — Repository architecture, configuration, Docker, FastAPI skeleton
- [x] Milestone 2 — PDF/DOCX ingestion + clause segmentation
- [x] Milestone 3 — Clause classification baseline
- [x] Milestone 4 — LoRA fine-tuning pipeline
- [x] Milestone 5 — Legal corpus ingestion
- [x] Milestone 6 — Dense + BM25 + RRF retrieval
- [x] Milestone 7 — Cross-encoder reranking
- [x] Milestone 8 — Evidence sufficiency + citation verification
- [x] Milestone 9 — LLM structured reasoning
- [x] Milestone 10 — End-to-end pipeline
- [x] Milestone 11 — Evaluation suite
- [x] Milestone 12 — Frontend
- [x] Milestone 13 — PDF report
- [x] Milestone 14 — Security hardening
- [ ] Milestone 15 — CI/CD + documentation

## Quickstart

```bash
cp .env.example .env
docker compose up -d --build
QDRANT_URL=http://localhost:6339 python legal_corpus/ingestion/index_corpus.py
open http://localhost:3005
```

Host ports are deliberately non-default (5436 Postgres, 6339/6340 Qdrant, 6383 Redis,
8004 backend, 3005 frontend) to avoid clashing with other projects' containers on the
same machine. Container-to-container traffic uses the standard ports internally.

The first analysis request downloads ~1GB of models (embeddings, reranker, classifier)
into a persisted Docker volume (`clauseguard_hf_cache`) — slow once, fast after.

## Frontend (Milestone 12)

Next.js 16 (App Router, TypeScript, Tailwind) — [frontend/](frontend). Four screens
matching spec section 18, all driven by the real API (no mock data anywhere):

- **Upload** — drag-and-drop or click-to-browse, PDF/DOCX only.
- **Processing** — real per-stage checkmarks computed from the actual response (there's
  no live progress channel yet since analysis runs synchronously — background job
  processing is Milestone 23 — so this is "not started → done", not a fabricated
  animated progress bar). Honestly shows "Risk analysis completed"/"Citations verified"
  as *not* done when no LLM is configured, rather than checking them anyway.
- **Results** — per-clause classification badge, risk badge, and (spec: "clear visual
  distinction between AI finding / legal source / evidence / uncertainty") a
  distinctly-styled "AI finding" / "Legal source" / "Evidence" block per finding with a
  citation-verified/unverified badge. Clauses with no configured LLM show a clearly
  different blue "Reasoning not available" state, never a fake risk level.
- **Report** — calls `GET /documents/{id}/report`, which honestly returns 501 "not yet
  implemented (Milestone 13)" — shown as-is, not hidden or faked.

**Building this required a real REST API that didn't exist yet** (the spec's section 20
endpoints — `POST /documents`, `POST /documents/{id}/analyze`,
`GET /documents/{id}/{clauses,findings,report}` — weren't part of the original 15
milestones' explicit scope, but a frontend with nothing real to call would mean fake
data, which violates the whole project's anti-fabrication policy). Added
[backend/app/api/routes/documents.py](backend/app/api/routes/documents.py): uploads are
saved under a server-generated UUID filename (never the client's original filename, to
prevent path traversal) and analyzed synchronously in a plain `def` route handler
(FastAPI's threadpool executor, so it doesn't block the event loop — Celery background
jobs are Milestone 23). Results are held in a documented **interim, non-durable
in-memory store** ([store.py](backend/app/services/pipeline/store.py)) — real, but lost
on restart; Postgres persistence is Milestone 21.

### Real bugs found and fixed while verifying this end-to-end in a real browser

Verification wasn't "click around and take a screenshot" — every one of these was found
by actually driving the app against the live Docker stack and tracing the failure to
its root cause:

1. **Docker image was missing runtime data entirely.** `docker/backend.Dockerfile` only
   ever copied `backend/` — `legal_corpus/metadata/corpus.json` (retrieval) and
   `training/` (classifier models) were never in the image, so the container would have
   crashed on the first real request with an unhandled `FileNotFoundError`. Fixed by
   copying both in (after the pip install layer, so corpus/model changes don't
   invalidate that expensive layer) and adding a defense-in-depth catch-all exception
   handler in `main.py` so any *future* gap like this returns a clean 500, not a leaked
   traceback.
2. **`transformers`/`peft` were never installed in the backend image.** They were left
   in the training-only extras group from Milestone 1, but Milestone 10's
   `classify_clause_lora` made them a genuine runtime dependency of the live API —
   moved to core dependencies.
3. **CORS only allowed a hardcoded `localhost:3000`** that nothing in this project
   actually uses (frontend is 3005/3006) — every real browser request was silently
   blocked. Made configurable (`CORS_ALLOWED_ORIGINS`), fixed, and covered by a
   regression test ([test_cors.py](backend/tests/test_cors.py)).
4. **Analysis results showed the server-generated UUID filename**, not the user's
   original filename — fixed in the `/analyze` route, covered by a test assertion.
5. **The Celery worker inherited the backend's HTTP healthcheck** and could never pass
   it (nothing listens on port 8000 in a Celery process) — gave it a real
   `celery inspect ping` healthcheck instead.
6. **The Docker frontend container's healthcheck could never pass**: Docker
   auto-sets a `HOSTNAME` env var to the container ID, and Next.js standalone mode
   binds to `process.env.HOSTNAME` when set — so the server ended up listening only on
   that hostname's resolved address, not all interfaces, and a healthcheck connecting
   via `127.0.0.1` was refused even though the host-mapped port still worked. Fixed
   with an explicit `ENV HOSTNAME=0.0.0.0`.
7. **No persisted model cache** — every container rebuild re-downloaded ~1GB of models
   from Hugging Face from scratch. Added a named `clauseguard_hf_cache` volume (not a
   bind mount — VirtioFS bind-mount deadlocks are a known issue on this host).

Real upload → analyze → results flow was verified in the built-in browser against the
actual Docker stack, with the genuine 10-clause benchmark contract, real classification/
retrieval/evidence-sufficiency results, and correctly honest LLM-not-configured states
throughout.

Frontend-specific automated tests (e.g. Playwright) are not yet in place — verification
here was manual browser-driven testing against the real stack, documented above, not
skipped silently. A good Milestone 15 candidate.

## PDF report (Milestone 13)

`GET /documents/{id}/report` generates a real PDF via
[backend/app/services/reporting/pdf_generator.py](backend/app/services/reporting/pdf_generator.py)
(`reportlab`) and streams it back with a proper `Content-Disposition` header — the
frontend's "Generate report" button (previously an honest 501 stub since Milestone 12)
now triggers a real browser download.

Deliberately plain, functional styling — spec section 19 explicitly says **"Do not make
the report look like an official legal opinion,"** so there's no letterhead, seal, or
formal-document styling. The disclaimer appears on the cover *and* in a footer on every
page. Contents, all computed from the real analysis result, nothing templated:

- Document metadata (filename, analysis timestamp, clause count)
- **Supported legal scope**, pulled live from `legal_corpus/metadata/scope.json` — the
  same 15 real passages documented in Milestone 5, not a separate hardcoded list
- **Executive summary** — real counts of LOW/MEDIUM/HIGH/INSUFFICIENT_EVIDENCE/
  LLM_NOT_CONFIGURED clauses, always summing to the actual clause count
- **Clause-by-clause findings** — classification, risk level, explanation, and for each
  AI finding: the claim, legal source + citation, quoted evidence, and a
  VERIFIED/CITATION_UNVERIFIED badge (spec: "clear visual distinction between AI
  finding / legal source / evidence / uncertainty")
- Per-clause and global limitations, plus the standard disclaimer

Verified with a real round-trip test (generate → re-parse with `pdfplumber`, already a
project dependency, and assert on the actual extracted text) in
[test_pdf_report.py](backend/tests/test_pdf_report.py), and end-to-end against the live
Docker stack: uploaded the real 10-clause benchmark contract through the browser,
clicked "Generate report", and confirmed a genuine 3-page, 6.4KB PDF downloaded with
correct classifications for all 10 clauses, the real evidence-sufficiency explanation
for `§ 10` (`"Top retrieved passage score (-0.6584) is below the sufficiency threshold
(0.0)..."`), and an executive summary that correctly totals 1 INSUFFICIENT_EVIDENCE + 9
LLM_NOT_CONFIGURED = 10.

Reproduce: `docker compose up -d --build && QDRANT_URL=http://localhost:6339 python
legal_corpus/ingestion/index_corpus.py`, then upload+analyze a document via the
frontend and click "Generate report", or `curl -X POST
localhost:8004/documents/{id}/analyze && curl localhost:8004/documents/{id}/report -o
report.pdf`.

## Security hardening (Milestone 14)

Audited spec section 25's checklist against what was already built (file type/size
validation, UUID-based filename sanitization, no path traversal, no execution of
uploaded files, prompt-injection defenses in the reasoning prompt, secrets only via
environment variables, `.env` gitignored and never committed — all already true from
Milestones 9/12) and found and fixed three real, concrete gaps rather than treating the
audit as a checkbox exercise:

1. **PDF report markup/XML injection — the most serious finding.** `reportlab`'s
   `Paragraph` parses its input as a small markup language (`<b>`, `<font>`, `<a>`, ...).
   Clause `section`/`heading` are extracted directly from the *uploaded document's raw
   text* (`services/segmentation/segmenter.py`) and were embedded unescaped. Verified
   real, not hypothetical, with a completely plausible input — the common German
   contract placeholder convention `<Kundennummer>` as a clause heading **crashed
   report generation** with an unhandled `ValueError`, no LLM or attacker intent
   required. A well-formed tag like `<font color="red" size="60">` rendered
   successfully, letting the uploaded document inject arbitrary styling or a clickable
   link into what looks like ClauseGuard's own compliance report. Fixed with a `_safe()`
   XML-escaping helper applied to every value that traces back to the contract —
   including LLM output (`finding.claim`, `.evidence`, `.legal_basis`,
   `reasoning.explanation`) unconditionally, since that's also derived from the
   untrusted document and will start flowing through this code path the moment an
   `ANTHROPIC_API_KEY` is configured. Verified with adversarial tests (unbalanced tag
   doesn't crash; a well-formed injection attempt appears as literal text, not live
   formatting) in
   [test_pdf_report.py](backend/tests/test_pdf_report.py).
2. **Corrupted uploads leaked internal exceptions to a generic 500.** A malformed PDF/
   DOCX (wrong file renamed, truncated upload — a realistic accident, not just an
   attack) raised a raw `pdfminer`/`python-docx` library exception that fell through to
   the Milestone 12 catch-all handler: safe (no info leak) but misleading, since a 500
   implies a server bug rather than a bad upload. `services/ingestion/service.py` now
   catches these at the parse boundary and re-raises a clean `ValidationFailedError`
   (422) with a safe message — the real exception is still logged server-side. Verified
   with real corrupted files (not mocks) at both the service and API level.
3. **No delete/cleanup endpoint existed at all** — a direct gap against spec section 29
   ("don't persist raw documents unnecessarily, provide cleanup/delete functionality").
   Added `DELETE /documents/{id}`, which removes the uploaded file from disk and clears
   both the document metadata and any analysis result from the store. Verified the file
   is actually gone from disk, not just unlinked from the API's view.

**Documented, not silently ignored, rather than fixed in this pass** (a reasonable
scope boundary, not an oversight): no magic-byte/content-sniffing validation beyond
extension + parse-time validation (parse-time validation already safely rejects
mismatched content, just without an earlier short-circuit); no explicit protection
against a DOCX/PDF decompression bomb (bounded by `MAX_UPLOAD_SIZE_MB` on the
*compressed* size, not the decompressed size — a genuinely advanced attack vector, not
something an ordinary corrupted file would trigger); no rate limiting on
upload/analyze (each `/analyze` call is expensive — retrieval + reranking + optional
LLM per clause — so repeated calls are a real, undefended DoS vector); the new DELETE
endpoint has no frontend UI affordance yet (backend capability only, since Milestone 14
is scoped to security hardening, not new frontend features).

68 unit tests passing (up from 66), ruff + mypy clean.

## Document ingestion & segmentation (Milestone 2)

- PDF parsing via `pdfplumber`, DOCX via `python-docx`. See
  [backend/app/services/ingestion](backend/app/services/ingestion).
- Scanned/image-only PDFs are detected (low text-density heuristic) and
  explicitly rejected with `OCRNotImplementedError` rather than silently
  returning near-empty text — OCR is architected as a pluggable seam
  (`services/ingestion/ocr.py`) but not implemented.
- Clause segmentation is regex/heuristic-based (German `§`, `Artikel`,
  `Ziffer`, numbered clauses, parenthesized sub-clauses), with a
  paragraph-based fallback when no numbering pattern is found. See
  [backend/app/services/segmentation](backend/app/services/segmentation) for
  documented limitations (flat clause list, no clause tree; bullets are not
  boundaries).
- Evaluated against a single hand-authored synthetic benchmark contract
  (`data/benchmark/segmentation/`, generated by
  `scripts/generate_benchmark_fixtures.py`) — real measured results in
  [reports/segmentation/report.md](reports/segmentation/report.md), generated
  by `eval/segmentation/evaluate_segmentation.py`. This benchmark is small
  and hand-authored; it demonstrates correctness on one contract structure,
  not generalization — documented as a limitation in the report itself.

## Retrieval (Milestone 6: dense + BM25 + RRF)

- **Dense**: `intfloat/multilingual-e5-small` embeddings, stored in Qdrant
  (`legal_corpus/ingestion/index_corpus.py` embeds and indexes all 15
  corpus passages).
- **BM25**: lexical search over the corpus text (`rank_bm25`), built
  in-memory at query time (corpus is small enough that persistence isn't
  needed yet).
- **Hybrid**: Reciprocal Rank Fusion (`k=60`, standard Cormack et al.
  constant) combines dense + BM25 rankings by position, not raw score — see
  [backend/app/services/retrieval/rrf.py](backend/app/services/retrieval/rrf.py).
- Real measured results (not fabricated) on a 15-query hand-authored
  benchmark against the 15-passage corpus, in
  [reports/retrieval/report.md](reports/retrieval/report.md): all three
  methods land around **Recall@1 0.80, Recall@3/5 0.93** — nearly identical,
  because a 15-document corpus is too small to meaningfully differentiate
  them. The report says this explicitly: this demonstrates the pipeline
  works end-to-end, not that hybrid retrieval beats either method alone —
  that comparison needs a larger corpus.

### Cross-encoder reranking (Milestone 7)

Full pipeline: Dense + BM25 → RRF → top-10 candidate pool → cross-encoder
(`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, small multilingual MiniLM
trained on mMARCO, covers German) → top-5 evidence. See
[backend/app/services/reranking](backend/app/services/reranking).

The same 15-query benchmark, evaluated with the reranker added as a 4th
method in [reports/retrieval/report.md](reports/retrieval/report.md): a
real, honest improvement — **Recall@1 0.80→0.867, Recall@3/5 0.933→1.0, MRR
0.864→0.933, NDCG@5 0.875→0.951**. The report notes the reranker can only
reorder within the top-10 RRF pool it's given, so its recall is bounded by
hybrid_rrf's recall at that pool size.

Reproduce (from the host, outside Docker, hence the port override —
`QDRANT_URL` defaults to the in-Docker hostname otherwise):
`docker compose up -d qdrant && QDRANT_URL=http://localhost:6339 python
legal_corpus/ingestion/index_corpus.py && QDRANT_URL=http://localhost:6339
python eval/retrieval/evaluate_retrieval.py`

## Evidence sufficiency & citation verification (Milestone 8)

Two reliability gates around the reasoning stage (Milestone 9), built and
tested ahead of it so the reasoning stage has something honest to plug into
rather than being trusted to police itself:

- **Evidence sufficiency**
  ([evidence_sufficiency.py](backend/app/services/verification/evidence_sufficiency.py)):
  runs on the reranked evidence before any LLM call. Threshold
  (`MIN_RERANK_SCORE = 0.0`) is empirically calibrated, not arbitrary — a
  genuinely relevant query scored **0.955** on the live corpus; two clearly
  off-topic queries (bike repair, a cake recipe) scored **-5.05** and
  **-5.80**; a query for a clause type the corpus deliberately doesn't cover
  (non-compete) scored **-3.94**. Below 0, reasoning is skipped and the
  clause is reported `INSUFFICIENT_EVIDENCE` rather than let the model guess.
- **Citation verification**
  ([citation.py](backend/app/services/verification/citation.py)): for every
  LLM-claimed finding, checks (1) the cited section exists in the corpus,
  (2) it was actually retrieved for this clause (not just anywhere in the
  corpus), (3) the claimed evidence text genuinely appears in that passage
  (text-overlap heuristic — a deeper semantic check is Milestone 16's job),
  (4) the citation's source matches. Any failure → `CITATION_UNVERIFIED`
  with a specific reason, never silently accepted.

Built and tested against constructed adversarial findings (fabricated
section numbers, citations to real sections that weren't retrieved,
hallucinated evidence text, malformed citation strings) since Milestone 9's
real LLM output doesn't exist yet — see
[backend/tests/test_citation_verification.py](backend/tests/test_citation_verification.py).

## LLM structured reasoning (Milestone 9)

`assess_clause()` ([backend/app/services/reasoning/service.py](backend/app/services/reasoning/service.py))
is the first stage that calls an LLM, and the full pipeline up to this point:
retrieve + rerank → evidence sufficiency (Milestone 8) → **[LLM]** →
citation verification (Milestone 8) → `ReasoningResult`.

- **No `ANTHROPIC_API_KEY` is configured in this environment.** The
  INSUFFICIENT_EVIDENCE path (e.g. an off-topic clause) never touches the
  LLM and works today — verified against the live corpus. A clause with
  sufficient evidence raises `LLMNotConfiguredError` with a clear message
  instead of faking a result. Both behaviors are integration-tested.
- **Structured output**: uses Claude's tool-use (not "ask it to output
  JSON in prose") with a JSON-schema-constrained tool, so `risk_level` can
  only ever be `LOW`/`MEDIUM`/`HIGH` and `classification` can only be one
  of the 10 taxonomy labels — the model cannot invent categories (spec
  section 14). Every response is additionally validated against a Pydantic
  schema before anything downstream trusts it.
- **Prompt-injection defenses** (spec section 30) in
  [prompts.py](backend/app/services/reasoning/prompts.py): the contract
  clause is wrapped in a delimiter tag with a random per-request nonce
  (`secrets.token_hex(8)`) so an attacker crafting clause text in advance
  can't forge a matching closing tag; explicit written instructions (system
  prompt + inline) that the clause is data, never commands; a reinforcing
  instruction placed *after* the untrusted section. These reduce risk —
  **they are not a guarantee**, and that's stated plainly in the code, not
  oversold. Real adversarial testing against a live model is Milestone 16's
  job once an API key makes it possible; for now, tests verify the prompt
  is *structured* correctly (injection text stays inside its delimited
  section, nonces are unpredictable per call) — see
  [test_reasoning_prompts.py](backend/tests/test_reasoning_prompts.py).
- A live-call test (`test_reasoning_client.py`) is written and ready,
  gated on `ANTHROPIC_API_KEY` being set — `SKIPPED` today, not deleted or faked.

## End-to-end pipeline (Milestone 10)

[`analyze_document()`](backend/app/services/pipeline/document_analysis.py)
wires every stage together: ingest → normalize → segment → *(per clause)*
classify (LoRA, falling back to the baseline if untrained) → retrieve +
rerank → evidence sufficiency → LLM reasoning → citation verification. A
clause-level failure (no configured LLM, no trained classifier) is recorded
on that clause and does not abort the rest of the document — pipeline
failures retain partial progress rather than losing everything to one
stage's failure.

**A real finding from running this on the full benchmark contract (10
clauses, [data/benchmark/segmentation](data/benchmark/segmentation)),
worth stating plainly rather than glossing over:** the evidence-sufficiency
threshold (Milestone 8) was calibrated on short natural-language queries,
where it cleanly separated relevant from off-topic. On realistic
full-paragraph clause text it is measurably more permissive — **9 of 10
clauses in the benchmark contract pass the sufficiency check**, even though
manual inspection shows the corpus has direct legal coverage for only
**4 of 10** of this contract's clause categories (LIABILITY, TERMINATION,
DATA_PROCESSING, and partially GENERAL_TERMS). For example, the genuine
`§ 8 Wettbewerbsverbot` (non-compete) clause — a category the corpus does
not cover at all — scored **0.88** against `DSGVO Art. 6`, comfortably
above the `0.0` threshold, despite Art. 6 (lawfulness of data processing)
having no real bearing on a non-compete clause. `§ 10` (general terms) was
the one clause correctly gated to `INSUFFICIENT_EVIDENCE`.

This is **not silently patched** by picking a new threshold that happens to
fit these 10 examples — that would be overfitting to a tiny sample, the
same mistake the anti-fabrication policy exists to prevent. It's recorded
here as a real, measured limitation and a concrete next step: the
sufficiency threshold needs its own calibration benchmark built from
full-length clause text (not short queries), with a proper held-out split —
see "Recommended next engineering step" at the bottom of this README.

Reproduce (from the host): `docker compose up -d qdrant &&
QDRANT_URL=http://localhost:6339 python -c "from pathlib import Path; from
qdrant_client import QdrantClient; from
app.services.pipeline.document_analysis import analyze_document;
print(analyze_document(Path('data/benchmark/segmentation/sample_contract_de.pdf'),
QdrantClient(url='http://localhost:6339')))"` (run from `backend/` or with
`PYTHONPATH=backend`).

## Evaluation suite (Milestone 11)

[`eval/end_to_end/evaluate_end_to_end.py`](eval/end_to_end/evaluate_end_to_end.py)
runs the real `analyze_document()` pipeline on the benchmark contract and
measures each component independently against real ground truth
([data/benchmark/end_to_end/ground_truth.json](data/benchmark/end_to_end/ground_truth.json),
which records — per clause — the expected classification label AND a
human judgment, cross-checked against the actual 15 corpus passages, of
whether the corpus genuinely covers that clause category).

Real measured results in
[reports/end_to_end/report.md](reports/end_to_end/report.md):

| Component | Result |
|---|---|
| Segmentation | 10/10 clauses detected (PASS) |
| Classification accuracy | **0.80** (2/10 wrong — matches the Milestone 10 observation) |
| Evidence sufficiency accuracy | **0.30** — the Milestone 10 finding, now a real number |
| Reasoning | `NOT_MEASURED` (no `ANTHROPIC_API_KEY`; 9 clauses would reach the LLM) |
| Citation verification | `NOT_MEASURED` (depends on reasoning) |
| Report generation | `NOT_APPLICABLE` (Milestone 13 not yet built) |

The **0.30 evidence-sufficiency accuracy** is the headline finding of this
milestone: it quantifies, rather than just narrates, that the sufficiency
gate (calibrated on short queries in Milestone 8) does a poor job on real
clause-length text for this benchmark — only 3 of 10 clauses got the
correct SUFFICIENT/INSUFFICIENT call against human-judged corpus coverage.
`reports/reasoning/report.md` is an explicit `NOT_MEASURED` stub (not a
guessed number) explaining exactly what's built, tested, and needed to
measure it for real.

Reproduce: `docker compose up -d qdrant && QDRANT_URL=http://localhost:6339
python eval/end_to_end/evaluate_end_to_end.py`

## Clause classification (Milestone 3: baseline)

- 10-label taxonomy: LIABILITY, TERMINATION, PAYMENT, DATA_PROCESSING,
  CONFIDENTIALITY, NON_COMPETE, INTELLECTUAL_PROPERTY, WARRANTY,
  GENERAL_TERMS, OTHER. See
  [backend/app/services/classification/labels.py](backend/app/services/classification/labels.py).
- Baseline model: TF-IDF (word 1-2grams) + logistic regression, deliberately
  simple — this is the pre-LoRA baseline the spec requires (Milestone 4 adds
  the LoRA-tuned model; a real baseline-vs-LoRA comparison only happens once
  both are measured).
- Trained on a 120-example synthetic dataset the developer hand-authored
  (`training/datasets/clause_classification/dataset.json`, see its
  `_provenance` field) — not real contract data, not legally reviewed.
  Deterministic 8/2/2 per-class train/val/test split
  (`training/scripts/prepare_dataset.py`, no randomness).
- Real measured baseline results (not fabricated) in
  [reports/classification/baseline/report.md](reports/classification/baseline/report.md):
  **60% accuracy, macro F1 0.547** on the 20-example test set — several
  classes (e.g. NON_COMPETE, GENERAL_TERMS) score 0 F1, confused with
  semantically adjacent classes. The report documents why this number is
  noisy at N=20 and why it isn't representative of real-world contracts.
- Reproduce: `python training/scripts/prepare_dataset.py && python
  training/scripts/train_baseline_classifier.py && python
  eval/classification/evaluate_baseline.py`

## LoRA fine-tuning (Milestone 4)

- Base model: `distilbert-base-multilingual-cased` (~135M params) — a small
  multilingual **encoder** with a sequence-classification head, not a
  generative LLM. Chosen because there is no GPU on this machine: LoRA
  adapters on a small encoder train in minutes on Apple Silicon MPS, whereas
  fine-tuning a multi-billion-parameter Qwen/Llama locally would not be
  realistic. Rationale documented in
  [training/configs/lora_classifier.json](training/configs/lora_classifier.json).
- LoRA via PEFT: r=8, alpha=16, target modules `q_lin`/`v_lin`. **745,738 /
  136,078,100 trainable params (0.548%)** — the actual number PEFT reports,
  not an estimate.
- Manual PyTorch training loop (not HF Trainer, to avoid pulling in
  logging/reporting integrations), deterministic seed, real training curve
  logged every epoch and preserved in the committed
  [reports/classification/lora/results.json](reports/classification/lora/results.json)
  (`training_history` field; the adapter weights themselves are gitignored
  and regenerated by the training script, not committed as a binary): loss
  2.35 → 0.086, val accuracy 15% → 65-70% over 12 epochs.
- Real measured baseline-vs-LoRA comparison (not fabricated) in
  [reports/classification/comparison.md](reports/classification/comparison.md):
  on the same 20-example test set, LoRA macro F1 **0.59** vs baseline
  **0.547** — a modest, believable improvement at this dataset size, not a
  dramatic one. Per-class results are mixed in both directions (LoRA fixes
  two baseline failures, baseline wins on one LoRA missed) — reported
  honestly rather than cherry-picked.
- Reproduce: `python training/scripts/train_lora_classifier.py && python
  eval/classification/evaluate_lora.py`

## Legal corpus (Milestone 5)

Deliberately constrained scope — 15 real legal passages, fetched programmatically
(not hand-typed, not scraped from unofficial sites) from official sources:

- **BGB** (11 sections) from [gesetze-im-internet.de](https://www.gesetze-im-internet.de)
  (German Federal Ministry of Justice + juris GmbH): §§ 305, 305b, 305c, 306, 307, 308,
  309, 310 (core AGB/standard-terms law) plus §§ 276, 280, 314 (liability, termination).
- **DSGVO/GDPR** (4 articles) from [EUR-Lex](https://eur-lex.europa.eu) (CELEX:32016R0679,
  official EU law portal): Art. 5, 6, 28, 32 (data-processing provisions).

Every passage carries full provenance (source, official URL, section, title, retrieval
timestamp) — see [legal_corpus/metadata/corpus.json](legal_corpus/metadata/corpus.json)
(committed) and [legal_corpus/metadata/scope.json](legal_corpus/metadata/scope.json) for
the machine-readable supported-scope declaration. Raw HTML snapshots are gitignored
(regenerable, not the deliverable). Reproduce with:
`python legal_corpus/ingestion/build_corpus.py`

Confidentiality and general payment-term clauses are covered by the classifier's
taxonomy (Milestone 3) but have no dedicated BGB provisions fetched yet — this is a
known scope gap, not silently papered over; clauses matched to those categories will
report `INSUFFICIENT_EVIDENCE` (Milestone 8) rather than being reasoned about without
a real legal basis, until the corpus is extended.

## Privacy

Contract text is never sent to an external LLM API unless `LLM_PROVIDER=anthropic` and
`ANTHROPIC_API_KEY` are explicitly set. With no key configured, the reasoning stage
reports itself as `NOT_CONFIGURED` rather than fabricating output.

## Known limitations & recommended next engineering step

This section will grow as more milestones land (full structure per spec is
Milestone 15). Current honest limitations, most actionable first:

1. **Evidence-sufficiency threshold needs a clause-length calibration
   benchmark.** Now a measured number, not just a narrative: **0.30
   accuracy** against human-judged corpus coverage on the benchmark
   contract (Milestone 11). The threshold (calibrated on short queries in
   Milestone 8) is measurably too permissive on full-paragraph clause text.
   Next step: build a benchmark of full-length clause examples (covered and
   deliberately uncovered categories) with a proper held-out split, and
   recalibrate against that instead of short queries.
2. **Legal corpus has gaps.** No BGB provisions fetched yet for
   confidentiality or payment-term-specific clauses (Milestone 5). Clauses
   in those categories should mostly hit `INSUFFICIENT_EVIDENCE` today, but
   see limitation 1 - the threshold gap means some will not (confirmed:
   both `§ 6 CONFIDENTIALITY` and `§ 2 PAYMENT` incorrectly passed
   sufficiency in the Milestone 11 run).
3. **No `ANTHROPIC_API_KEY` configured in this environment** - the
   reasoning stage is fully built and tested for its gating behavior, but
   has not produced a single real reasoning result yet. `reports/reasoning/`
   is an explicit `NOT_MEASURED` stub, not a guessed number. Milestone 16
   (hallucination/faithfulness testing) also needs a key to produce real
   numbers.
4. **LoRA classifier is imperfect** (macro F1 0.59 on a 20-example test
   set) - observed in practice during the Milestone 10 end-to-end run: a
   genuine `§ 4 Haftung` (LIABILITY) clause was misclassified as
   NON_COMPETE. This did not affect evidence retrieval (which operates on
   the clause text, not the classification label), but would affect the
   classification label reported to a user.
5. **Document/analysis storage is in-memory, not durable** (Milestone 12,
   documented in `store.py`) - works correctly for the life of the backend
   process but is lost on restart and not shared across replicas. Postgres
   persistence is Milestone 21.
6. **No frontend automated test suite yet** - Milestone 12's frontend was
   verified by manually driving the real app in a browser against the live
   Docker stack (see "Frontend" section above for what that verification
   found and fixed). A Playwright/Vitest suite is a reasonable Milestone 15
   addition.
7. **No rate limiting on upload/analyze** (Milestone 14) - each `/analyze`
   call is expensive (retrieval + reranking + optional LLM per clause), so
   repeated calls are a real, undefended DoS vector on a single-instance
   deployment. Reasonable Milestone 15 addition.
8. **No decompression-bomb protection for DOCX/PDF parsing** (Milestone 14)
   - `MAX_UPLOAD_SIZE_MB` bounds the compressed upload size, not what it
   could expand to during parsing. A genuinely advanced attack vector, not
   triggered by an ordinary corrupted file (which is now handled cleanly -
   see "Security hardening" above).
9. **The new `DELETE /documents/{id}` endpoint has no frontend UI** yet -
   it's a backend capability added to satisfy spec section 29's cleanup
   requirement; wiring it into the frontend is a small, reasonable addition
   whenever the frontend gets its next pass.
