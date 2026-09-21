# Evidence-sufficiency calibration report (Milestone 16)

Generated from `eval/evidence_sufficiency/calibrate.py`, which reads real
`retrieve_and_rerank()` scores captured in `scored_dataset.json` (built by
`eval/evidence_sufficiency/score_dataset.py` against the live Qdrant corpus - no score
in this report is simulated or hand-typed). This report now covers two sessions of
work; see `phase1_inspection.md` (including its addendum) for what was inspected
before each session's changes, and `error_analysis.md` for the per-clause failure
breakdown.

## The question

> Given a contract clause and retrieved legal evidence, can ClauseGuard reliably
> determine whether there is sufficient evidence to proceed with legal-risk reasoning?

## Session 1: length-penalty recalibration (0.30 → 0.60 on the original benchmark)

The original gate (`MIN_RERANK_SCORE = 0.0` on the raw cross-encoder top score) was
calibrated on 4 short standalone queries and measured **0.30 accuracy** on the real
10-clause end-to-end benchmark. A 40-example calibration dataset (35 conclusive)
confirmed the cross-encoder's raw score is measurably inflated by clause length. A
**logarithmic length penalty** (`score - alpha * log(length)`) was selected after a
linear-penalty candidate was caught having an identical confusion matrix to the
baseline on the full population - it only relocated errors, it didn't reduce them.
Result: held-out test accuracy 0.70→0.90, full-population accuracy 0.714→0.886,
**original benchmark accuracy 0.30→0.60**.

## Session 2 (this report): does a score-gap feature help further?

**Hypothesis** (stated up front, not retrofitted): a large gap between the top-ranked
and second-ranked retrieved passage plausibly indicates one genuinely dominant, specific
legal match, independent of clause length - this might catch cases the length penalty
alone still gets wrong.

### Dataset growth (Phase 2)

Grown from 35 to **49 conclusive examples** (54 total incl. 5 AMBIGUOUS), with every
new example grounded in previously-unused real corpus text - BGB §305c (surprising/
ambiguous clauses), §310 (B2B scope of AGB law), DSGVO Art. 5 (processing principles),
Art. 6 (lawful basis) - not random padding. New examples specifically target: thin
categories (PARTIAL grew 4→6, TERMINATION 3→5, INTELLECTUAL_PROPERTY 2→3), and the
score-gap hypothesis itself (`hybrid_topic_liability_dataprocessing`, a clause
genuinely covered by TWO corpus passages at once, deliberately included to test
whether the gap feature would incorrectly penalize real multi-topic coverage).

### Split (Phase 3-4)

Same stratified-by-`coverage_type`, seeded (`seed=42`) methodology as session 1, now
on the larger pool: **calibration=23, validation=13, test=13**
(`reports/evidence_sufficiency/results.json`'s `dataset.class_distribution_by_split`
and `.length_distribution_by_split` give the full breakdown). N=49 is still small -
stated plainly, not hidden.

### What was compared (Phase 4-6)

Two candidates, **both refit from scratch on the new split** (so neither is
artificially favored by having been tuned on more or less data):

1. **Current method**: logarithmic length penalty alone, `score - alpha*log(length)`.
2. **Current method + score gap**: `score - alpha*log(length) + beta*(top_score -
   second_score)`.

Fit on `calibration`, selected on `validation` (recall floor ≥0.7, then minimize
false-positive rate, then maximize accuracy - same objective as session 1). The
score-gap variant was required to clear **two** bars before adoption, not one:

- Beat the length-only method on the **true held-out test split** (scored once, never
  re-tuned to it).
- **Not regress** the full-population sanity check (the same discipline that caught
  and discarded session 1's linear-penalty candidate).

### Result: ADOPTED

| | Held-out test (n=13) | Full population (n=49) |
|---|---|---|
| Raw baseline (original, pre-M16) | accuracy 0.692, FPR 0.600 | accuracy 0.755, FPR 0.471 |
| Current method (log penalty, refit) | accuracy 0.692, FPR 0.400 | accuracy 0.796, FPR 0.294 |
| **Current method + score gap** | **accuracy 0.769, FPR 0.200** | **accuracy 0.857, FPR 0.059** |

The score-gap variant won on held-out test with **no recall cost there** (same 6 true
positives, same 2 false negatives as the length-only method - it converted one false
positive into a true negative and nothing else changed). On the full population it
also improved accuracy and cut the false-positive rate roughly 5x, at a modest real
cost: recall dropped from 0.844 to 0.813 (one additional missed genuinely-covered
clause - see `error_analysis.md` for exactly which one and why).

### By clause length (Phase 5)

| Bucket | Raw baseline FPR | Length-penalty-only FPR | Length + score-gap FPR |
|---|---|---|---|
| SHORT | 0.0 | 0.0 | 0.0 |
| MEDIUM | 0.4 | 0.2 | **0.0** |
| LONG | **1.0** | 0.667 | **0.167** |

The score-gap feature's biggest win is exactly where the original problem was worst:
LONG clauses. False-positive rate there went from 100% (uncalibrated) to 66.7%
(length penalty alone) to 16.7% (length + score gap) - a real, substantial, verified
improvement, not a claim.

### On the original, untouched 10-clause end-to-end benchmark

| | Accuracy |
|---|---|
| Original (uncalibrated) | 0.30 |
| Session 1 (length penalty) | 0.60 |
| **Session 2 (length penalty + score gap)** | **0.70** |

§5 (WARRANTY, genuinely uncovered) flipped from an incorrect false positive to
correct - and, unlike session 1's recalibration (which introduced one regression on
this same benchmark, §3), **session 2 introduced zero new regressions on this
benchmark**. §3 (TERMINATION) and §10 (GENERAL_TERMS/severability) remain incorrect,
carried over unchanged from session 1 - not silently dropped, see `error_analysis.md`.

## What this is not

Not solved. N=49 conclusive examples is still small, the held-out test split is 13
examples, and the score-gap feature has a real, disclosed cost: it introduced two new
false negatives on genuinely-covered clauses whose top-2 retrieved passages were both
legitimately relevant (see `error_analysis.md` - this is exactly the failure mode
`hybrid_topic_liability_dataprocessing` was designed to probe, and while that specific
example survived correctly, two *other* examples did not). This remains the single
most important reliability caveat in the project - see the README's Limitations
section.
