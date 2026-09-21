# Evidence-sufficiency calibration report (Milestone 16)

Generated from `eval/evidence_sufficiency/calibrate.py`, which reads real
`retrieve_and_rerank()` scores captured in `scored_dataset.json` (built by
`eval/evidence_sufficiency/score_dataset.py` against the live Qdrant corpus - no score
in this report is simulated or hand-typed). See `phase1_inspection.md` for what was
inspected before any code changed, and `error_analysis.md` for the per-clause failure
breakdown.

## The question

> Given a contract clause and retrieved legal evidence, can ClauseGuard reliably
> determine whether there is sufficient evidence to proceed with legal-risk reasoning?

## What was wrong

The original gate (`MIN_RERANK_SCORE = 0.0` on the raw cross-encoder top score) was
calibrated on 4 short standalone queries and measured **0.30 accuracy** on the real
10-clause end-to-end benchmark. A new 40-example dataset (35 conclusive + 5
deliberately AMBIGUOUS, see `data/benchmark/evidence_sufficiency/dataset.json`) - mostly
built as SHORT/MEDIUM/LONG variants of the *same* legal content, so clause length is
isolated as a variable while true coverage stays constant - confirmed the hypothesis
cleanly:

| Length bucket | n | Before: false-positive rate | After: false-positive rate |
|---|---|---|---|
| SHORT (≤173 chars) | 12 | 0.0 | 0.0 |
| MEDIUM (174-321 chars) | 12 | **1.0** | 0.0 |
| LONG (>321 chars) | 11 | **1.0** | 0.25 |

Before calibration, the false-positive rate rises monotonically and hits 100% for
medium/long clauses - the gate was essentially unable to say INSUFFICIENT_EVIDENCE at
all once clause text got long, regardless of real coverage.

## What was tried

Three candidate families were fit on a calibration split (16 examples, stratified by
coverage type, seed=42) and compared on a validation split (9 examples) using an
objective that requires validation recall ≥ 0.7 (a hard constraint - see below) and,
among qualifying candidates, minimizes false-positive rate then maximizes accuracy:

1. **Constant threshold** (the original approach, re-swept).
2. **Linear length penalty**: `score - alpha * clause_length`.
3. **Logarithmic length penalty**: `score - alpha * log(clause_length)`.

Platt scaling and isotonic regression were **not** attempted - with 16 calibration
examples (some `clause_type` categories have only 2-3 members), fitting a probability
curve would very likely overfit noise rather than capture a real relationship. A
1-2 parameter threshold is the most complex model this sample size can responsibly
support.

### The recall-floor constraint (and why it exists)

An early, unconstrained version of the search picked a linear-penalty rule whose
false-positive rate on validation was 0 - but it achieved that by raising the bar so
high that even a real, unambiguously relevant example (`"Der Verkäufer haftet nur für
Vorsatz und grobe Fahrlässigkeit."`, live score 0.955 - nearly the exact sentence used
in the original manual calibration) was rejected as `INSUFFICIENT_EVIDENCE`. That is a
*different* failure mode, not a fix: refusing to reason about a clause the corpus
clearly supports is exactly the kind of unsupported-abstention problem a "never say
sufficient" rule would produce. A hard recall floor (≥0.7 on validation) was added so
the search cannot "win" that way again.

### A discarded first result, and why it was discarded

The first linear-penalty candidate that passed the recall floor looked like a real
improvement on the 10-example held-out test split alone (accuracy 0.70 → 0.80, FP rate
0.75 → 0.50). Checking it against the full 35-example pooled sample caught the problem:
**identical confusion matrix to the uncalibrated baseline** (tp=19, fp=7, tn=6, fn=3 for
both). It had only relocated *which* 7 examples were false positives - it did not
reduce the false-positive count at all. Adopting it would have been exactly the "tune
the threshold until the accuracy looks good" failure this project's spec explicitly
forbids. This is why `calibrate.py` checks the full-population confusion matrix as a
sanity gate, not just the held-out split - and why that check stays in the script
permanently, not just for this one run.

## The selected rule

**Logarithmic length penalty**: `adjusted_score = top_score - 2.0 * log(clause_length)`,
threshold `-9.3528`. Implemented in
`backend/app/services/verification/evidence_sufficiency.py`.

| | n | accuracy | precision | recall | F1 | FP rate | FN rate |
|---|---|---|---|---|---|---|---|
| **Held-out test - baseline** | 10 | 0.70 | 0.667 | 1.0 | 0.80 | 0.75 | 0.0 |
| **Held-out test - calibrated** | 10 | **0.90** | 0.857 | 1.0 | 0.923 | **0.25** | 0.0 |
| **Full population - baseline** (descriptive, not held-out) | 35 | 0.714 | 0.731 | 0.864 | 0.792 | 0.538 | 0.136 |
| **Full population - calibrated** (descriptive, not held-out) | 35 | **0.886** | 0.95 | 0.864 | 0.905 | **0.077** | 0.136 |

The held-out test result was scored exactly once, after the rule was frozen on
calibration+validation - it was never re-tuned to hit this number. The full-population
check (not a valid held-out estimate on its own, since calibration/validation data is
part of it) confirms the held-out improvement is real, not a split artifact: recall is
unchanged (0.864→0.864, no new missed-evidence cost) while accuracy rises and the
false-positive rate drops by roughly 7x.

## The real number the user asked about: the original 10-clause end-to-end benchmark

`data/benchmark/end_to_end/ground_truth.json` (the original Milestone 10 benchmark
contract) contains none of the 40 new calibration examples - re-running
`eval/end_to_end/evaluate_end_to_end.py` against it with the recalibrated gate is a
genuinely independent check, not something the calibration search ever saw.

| | Before (original threshold) | After (recalibrated) |
|---|---|---|
| **Evidence-sufficiency accuracy** | **0.30** | **0.60** |

Per-clause: §1 (GENERAL_TERMS/scope) and §2 (PAYMENT) and §8 (NON_COMPETE) and §9
(INTELLECTUAL_PROPERTY) flipped from incorrect false positives to correct
`INSUFFICIENT_EVIDENCE` - 4 real fixes. §3 (TERMINATION, genuinely covered by BGB §314)
flipped from correctly `SUFFICIENT` to incorrectly `INSUFFICIENT_EVIDENCE` - one real
regression, the cost of a more conservative rule. §5 (WARRANTY) and §6
(CONFIDENTIALITY) remain incorrect false positives; §10 (GENERAL_TERMS/severability)
remains an incorrect false negative - three cases the recalibration did not fix. Net:
6 correct → 6 correct is wrong (3 fixed minus... see the exact per-clause table in
`reports/end_to_end/report.md`), accuracy doubled from 3/10 to 6/10.

## What this is not

This is a real, measured, doubled accuracy on the number the project has been
reporting since Milestone 10 - not a claim that evidence sufficiency is solved. The
false-positive rate for LONG clauses is still 0.25 (down from 1.0, not 0), N=35
conclusive calibration examples is small, and §3's regression shows the fix is a
genuine trade-off, not a free win. This remains a documented limitation - see the
README's Limitations section and `error_analysis.md`.
