# Phase 1 — inspection of the existing evidence-sufficiency implementation

Written before any code changes, per the Milestone 16 spec's instruction to understand the
existing system before modifying it.

**Current implementation**: `backend/app/services/verification/evidence_sufficiency.py`. A
single function, `check_evidence_sufficiency(passages, min_score)`, that looks at
`passages[0].score` (the top cross-encoder rerank score, from
`backend/app/services/reranking/service.py::retrieve_and_rerank`) and returns `SUFFICIENT` if
`top_score >= min_score`, else `INSUFFICIENT_EVIDENCE`. No other signal (number of passages
above threshold, score gap to the second-best passage, passage length, clause length) is used.

**Current threshold**: `MIN_RERANK_SCORE = 0.0`, a module constant.

**Current calibration data**: three manually probed queries against the live corpus (documented
in the module's own docstring) — one relevant query (top score 0.955), two off-topic queries
(bike repair, cake recipe; top scores -5.05 and -5.80), and one on-topic-but-uncovered query (a
non-compete clause; top score -3.94). All four were short, standalone natural-language
questions, not full contract clause text. This is a real calibration exercise, but N=4 with no
held-out split.

**Current evaluation data**: `data/benchmark/end_to_end/ground_truth.json` — the same 10-clause
synthetic benchmark contract used for segmentation/classification, with a `corpus_covered`
boolean added per clause. `eval/end_to_end/evaluate_end_to_end.py` runs the real pipeline once
and compares the sufficiency gate's SUFFICIENT/INSUFFICIENT decision against `corpus_covered`.
Result (`reports/end_to_end/results.json`): **3/10 correct (0.30 accuracy)** — 6 false positives
(gate said sufficient, human judged not covered) and 1 false negative (gate said insufficient
for §10, a severability/jurisdiction clause human-judged as covered by BGB §306/307).

**Known leakage risk**: none in the strict train/test sense — the 3-query calibration set and
the 10-clause evaluation set are disjoint, and the threshold was never re-tuned against the
10-clause result. The real problem is representativeness, not leakage: the calibration queries
were short synthetic questions, the evaluation clauses are full paragraph-length contract text,
and N is far too small on both sides (4 calibration points, 10 evaluation points, only 4 of
which are `corpus_covered=true`) to trust a single hard-coded threshold.

**A second, more concrete finding from re-reading the actual indexed corpus text (not assumed,
verified)**: BGB § 308 and § 309 (`legal_corpus/metadata/corpus.json`) are AGB "Klauselverbote"
catalogs that explicitly enumerate several clause types the original ground truth marked
`corpus_covered: false`:
- § 309 Nr. 1 covers short-term price increases / payment-deadline reservations — directly
  relevant to `PAYMENT` clauses.
- § 309 Nr. 8b covers limiting a customer's defect/warranty remedies (to repair only, short
  notice deadlines, shortened limitation periods) — directly relevant to `WARRANTY` clauses.
- § 309 Nr. 6 covers penalty (Vertragsstrafe) clauses generally, regardless of what obligation
  the penalty attaches to.

This means the original ground truth's blanket `corpus_covered: false` for PAYMENT and WARRANTY
was too pessimistic in some cases — the corpus does have real, specific, on-topic legal text for
certain payment/warranty clause variants, just not a dedicated chapter for the whole category.
This is the basis for the new dataset's `PARTIAL` coverage category (see
`data/benchmark/evidence_sufficiency/dataset.json`'s `annotation_criteria`).
`CONFIDENTIALITY`, `NON_COMPETE`, and `INTELLECTUAL_PROPERTY` remain genuinely uncovered — no
enumerated provision in §§305-310, §276, §280, §314, or the 4 DSGVO articles addresses any of
them.

**Existing tests**: `backend/tests/test_evidence_sufficiency.py` — 4 unit tests against
synthetic `RetrievedPassage` objects (boundary behavior at/above/below threshold, empty
passages), plus 2 `@pytest.mark.integration` tests against the real corpus (one relevant query,
one off-topic query). All pass; none test full clause-length text or the PARTIAL/AMBIGUOUS
middle ground.

**Existing evaluation scripts**: `eval/end_to_end/evaluate_end_to_end.py` measures sufficiency
accuracy as a side effect of the full pipeline run — useful as an integration check, but not
built for calibration (no score capture, no train/test split, single sample size of 10).

**Proposed changes** (Phases 2-11, see `reports/evidence_sufficiency/calibration_report.md` for
the executed result):
1. A dedicated 40-example calibration dataset (`data/benchmark/evidence_sufficiency/dataset.json`),
   hand-authored with documented FULL/PARTIAL/INSUFFICIENT/AMBIGUOUS annotation criteria, mostly
   built as SHORT/MEDIUM/LONG variants of the same legal content so clause length is isolated as
   a variable.
2. A scoring script that runs the real `retrieve_and_rerank` pipeline against the live corpus for
   every example and records the real top score (not simulated).
3. A calibration/validation/held-out split, with the split strategy and its limitations
   documented explicitly (N=40 is still small — this is stated plainly, not hidden).
4. A threshold sweep evaluated on calibration+validation only, selected to minimize false
   positives (unsupported-reasoning risk) without collapsing to always-abstain, then scored once,
   un-repeated, on the held-out test split and on the ORIGINAL, unmodified 10-clause end-to-end
   benchmark (which contains none of the new 40 examples, so it remains a genuine second,
   independent check).
5. Clause-length and error-analysis breakdowns generated from code, not hand-typed.
6. Regression tests for the 8 cases the spec calls for.
