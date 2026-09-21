# Evidence-sufficiency error analysis (Milestone 16)

Every example below is from the full 35-example conclusive pool (calibration +
validation + test combined - the held-out test split alone is too small, 10 examples,
to support a useful error analysis on its own). Scores are real
`retrieve_and_rerank()` output from `scored_dataset.json`.

## Baseline (original threshold=0.0, no length adjustment) - 10 errors

| clause_id | error type | coverage | length | top_score | likely cause |
|---|---|---|---|---|---|
| general_terms_scope_medium | false positive | INSUFFICIENT | MEDIUM | 0.060 | Length-driven score inflation on a genuinely-uncovered topic - just barely over 0.0. |
| general_terms_scope_long | false positive | INSUFFICIENT | LONG | 3.248 | Length-driven score inflation, more severe at greater length. |
| confidentiality_medium | false positive | INSUFFICIENT | MEDIUM | 1.450 | Length-driven score inflation - no confidentiality-specific passage exists in the corpus at all. |
| confidentiality_long | false positive | INSUFFICIENT | LONG | 4.765 | Length-driven score inflation, the most severe case in the dataset. |
| non_compete_long | false positive | INSUFFICIENT | LONG | 0.073 | Length-driven score inflation on a topic with no corpus coverage. |
| non_compete_lexical_trap | false positive | INSUFFICIENT | MEDIUM | 1.585 | **Overly broad similarity / irrelevant retrieved passage**: heavy reuse of "Kündigung"/"Vertrag" vocabulary pulled a high score from BGB §314 (termination) despite the clause being about a legally distinct question (post-contractual competition restriction) that §314 does not address. |
| ip_assignment_long | false positive | INSUFFICIENT | LONG | 2.256 | Length-driven score inflation on a topic with no corpus coverage. |
| payment_deadline_short | false negative | PARTIAL | SHORT | -0.399 | **Threshold problem, not a retrieval failure**: BGB §308 Nr.1a is genuinely relevant to short payment-deadline clauses, but the raw threshold (0.0) sits above what a short, generically-worded PARTIAL-coverage clause can score. |
| payment_deadline_medium | false negative | PARTIAL | MEDIUM | -0.552 | Same threshold problem as above - PARTIAL coverage produces a real but modest score that a flat threshold under-credits. |
| penalty_for_confidentiality_breach | false negative | PARTIAL | SHORT | -3.372 | **Retrieval failure, not a threshold problem**: BGB §309 Nr.6 (Vertragsstrafe) is the real legal basis for this clause's penalty mechanism, but the query's confidentiality-breach framing dominates retrieval and the penalty-specific passage never surfaces with a competitive score. A threshold change alone cannot fix this - it needs better retrieval for this case, or a query-rewriting step that isolates the enforcement-mechanism sub-topic from the substantive-obligation topic. |

**Pattern**: 7 of 10 baseline errors are false positives, and all 7 are explained by
the same length-driven score inflation, confirming the Milestone 10/11 hypothesis
directly. The 3 false negatives are PARTIAL-coverage cases where a flat threshold
under-credits real-but-modest evidence - a genuinely different cause from the false
positives.

## Calibrated (logarithmic length penalty) - 4 errors

| clause_id | error type | coverage | length | top_score | likely cause |
|---|---|---|---|---|---|
| confidentiality_long | false positive | INSUFFICIENT | LONG | 4.765 | **Still a threshold problem**: 4.765 is high enough that even the log penalty (which removes roughly `2.0 * log(585) ≈ 12.9` points) doesn't fully compensate. This is the single most length-inflated score in the dataset - the length correction helps but doesn't fully cancel it. |
| payment_deadline_long | false negative | FULL | LONG | 0.495 | **Regression, threshold problem**: this clause's LONG variant has real, specific coverage (BGB §309 Nr.2/3, not just the generic §308 relevance of the short/medium variants - see dataset.json's coverage_note), but its raw score (0.495) is modest for its length, and the log penalty - tuned to suppress genuinely-uncovered long clauses - also suppresses this genuinely-covered one. A cost of using one length-conditioned rule for both directions. |
| penalty_for_confidentiality_breach | false negative | PARTIAL | SHORT | -3.372 | Unchanged from baseline - see above, this is a retrieval failure, not something any threshold/length adjustment on the EXISTING score can fix. |
| payment_deadline_medium | false negative | PARTIAL | MEDIUM | -0.552 | Unchanged from baseline - real PARTIAL evidence, modest score, still below the (length-adjusted) bar for a medium-length clause. |

**What actually got fixed** (7 cases, all real): `confidentiality_medium`,
`general_terms_scope_long`, `general_terms_scope_medium`, `ip_assignment_long`,
`non_compete_lexical_trap`, `non_compete_long`, `payment_deadline_short`. Notably this
includes the lexical-overlap adversarial case (`non_compete_lexical_trap`) - the length
penalty fixed it as a side effect, not because the penalty specifically targets lexical
overlap, which is worth being honest about: it worked here, but a differently-worded
lexical-trap example at a shorter length would likely still fool the gate, since lexical
overlap and clause length are different problems that happened to co-occur in this one
example.

**What got worse** (1 case): `payment_deadline_long` - a real, disclosed regression, not
hidden. The single most useful next step this points to (see README's Future Work) is a
signal beyond raw score + length, e.g. the score gap to the second-best retrieved
passage (a large gap plausibly indicates a genuinely dominant, specific match regardless
of length), which N=35 is too small to calibrate responsibly today.

**What's still wrong** (3 cases, honestly unresolved): `confidentiality_long` (false
positive - the corpus has no confidentiality coverage at all, but the score is too high
for any length-only penalty to fully suppress), `payment_deadline_medium` and
`penalty_for_confidentiality_breach` (false negatives - real PARTIAL evidence that a
single global threshold under-credits). None of these were silently dropped from the
dataset or reported around - they are the honest remainder.

## Ambiguous examples (excluded from accuracy, reported here for transparency)

| clause_id | top_score | baseline says | calibrated says | note |
|---|---|---|---|---|
| data_processing_vague | 1.716 | SUFFICIENT | SUFFICIENT | Both agree; whether that's "right" is genuinely undecidable from the clause text alone - see dataset.json's coverage_note. |
| hybrid_liability_warranty | 0.284 | SUFFICIENT | INSUFFICIENT_EVIDENCE | The two rules disagree - a real example of the calibration changing an outcome where there was no confident ground truth to begin with. |
| vague_risk_allocation | -2.574 | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | Both agree. |
| jurisdiction_only | -1.371 | INSUFFICIENT_EVIDENCE | SUFFICIENT | The two rules disagree. |
| schriftform_clause | 0.238 | SUFFICIENT | SUFFICIENT | Both agree. |

No forced true/false label was invented for these 5 examples - see `dataset.json`'s
`annotation_criteria` for why. They are included here so the calibration's behavior on
genuinely hard cases is visible, not swept out of the sample.
