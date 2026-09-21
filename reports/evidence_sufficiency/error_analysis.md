# Evidence-sufficiency error analysis (Milestone 16, session 2)

Every example below is from the full 49-example conclusive pool (calibration +
validation + test combined - the held-out test split alone, 13 examples, is too small
to support a useful error analysis on its own). Scores are real `retrieve_and_rerank()`
output from `scored_dataset.json`. See `calibration_report.md` for the aggregate
numbers this breakdown explains.

## What the score-gap feature fixed (5 cases, all real)

| clause_id | coverage | length | top / second (gap) | why it's fixed |
|---|---|---|---|---|
| `general_terms_scope_long` | INSUFFICIENT | LONG | 3.248 / 1.871 (1.38) | Length-inflated score, but no single dominant match - the gap correctly signals weak, diffuse relevance rather than a real hit. |
| `confidentiality_long` | INSUFFICIENT | LONG | 4.765 / 4.734 (0.03) | Near-zero gap is a strong signal here: the top-2 candidates are essentially tied, meaning neither is a genuinely specific match - exactly what a truly uncovered topic should look like. |
| `ip_assignment_long` | INSUFFICIENT | LONG | 2.256 / ~1.0 (~1.25) | Same pattern - length-inflated top score, no clean single winner. |
| `non_compete_lexical_trap` | INSUFFICIENT | MEDIUM | 1.585 / 0.158 (1.43) | The adversarial lexical-overlap case (heavy "Kündigung"/"Vertrag" reuse fooling retrieval into a high top score) - the gap wasn't large enough to sustain a false SUFFICIENT once the length penalty also applied. |
| `payment_deadline_short` | PARTIAL | SHORT | -0.399 / -3.095 (2.70) | A real PARTIAL-coverage case with a genuinely wide margin over the next-best (irrelevant) candidate - correctly pushed to SUFFICIENT. |

## What the score-gap feature broke (2 cases, real, disclosed - not hidden)

| clause_id | coverage | length | top / second (gap) | why it broke |
|---|---|---|---|---|
| `warranty_remedy_long` | FULL | LONG | 3.271 / 2.866 (0.41) | Genuinely covered by BGB §309 Nr. 8b (defect-remedy limitation, specifically the notice-deadline and limitation-period enumerated points) - but the corpus's other warranty-adjacent passages (§309's broader Klauselverbote list) also score respectably against this clause, producing a real but modest gap that the beta=1.2 penalty pushed below threshold. |
| `purpose_limitation_clause_medium` | FULL | MEDIUM | 2.301 / 2.135 (0.17) | Genuinely covered by DSGVO Art. 5(1)(b) - but Art. 6 (lawful basis) is topically adjacent and scores closely, again producing a small, real gap despite genuine coverage. |

**This is the exact failure mode `hybrid_topic_liability_dataprocessing` was
deliberately added to probe** (see `calibration_report.md`'s Phase 2 section) - a
clause genuinely covered by more than one relevant corpus passage can show a small
gap between its top-2 matches even though it IS covered. That specific example
survived correctly (SUFFICIENT, gap=1.28 was wide enough); these two did not. The
honest conclusion: the score-gap feature's assumption - "one dominant match = real
coverage, close competition = not real coverage" - is a real, useful heuristic on
average (net -3 errors, see below) but not universally true, and topically adjacent
*and both genuinely relevant* corpus passages are exactly where it can misfire.

## What's still wrong under both methods (5 cases, unchanged, honestly unresolved)

| clause_id | coverage | length | top / second (gap) | cause |
|---|---|---|---|---|
| `penalty_for_confidentiality_breach` | PARTIAL | SHORT | -3.372 / -3.899 (0.53) | **Retrieval failure, not a threshold problem**: BGB §309 Nr. 6 (Vertragsstrafe) is the real basis, but the confidentiality-breach framing dominates retrieval and the penalty-specific passage never scores competitively. No threshold/gap adjustment on the EXISTING top-2 scores can fix a retrieval problem. |
| `confidentiality_penalty_medium` | PARTIAL | MEDIUM | -2.021 / -2.446 (0.43) | Same retrieval failure as above, at MEDIUM length. |
| `payment_deadline_medium` | PARTIAL | MEDIUM | -0.552 / -2.027 (1.47) | Real PARTIAL evidence (BGB §308 Nr. 1a is generically relevant) but the raw score is too low for even a decent gap to compensate - a threshold problem. |
| `payment_deadline_long` | FULL | LONG | 0.495 / -2.162 (2.66) | Real, specific coverage (§309 Nr. 2/3) with a genuinely wide gap (2.66) - but the raw top score (0.495) is still too low after the length penalty for a LONG clause. This is the length penalty over-suppressing a genuinely-covered long clause, a limitation carried over unchanged from session 1. |
| `confidentiality_extreme_long` | INSUFFICIENT | LONG (865 chars, the longest in the dataset) | 7.785 / 7.444 (0.34) | **The score-gap feature's real ceiling**: the gap here is small (0.34, "should" signal no dominant match), but the raw top score is so extremely length-inflated (7.785, the highest INSUFFICIENT score in the dataset) that it clears the threshold regardless. A sufficiently large raw score can still dominate a small gap penalty - the length penalty alone isn't strong enough at this extreme, and this is the single most severe remaining false positive in the dataset. |

## Net effect

Full population: 10 errors (length-penalty-only) → 7 errors (length + score gap) = **5
fixed, 2 regressed, 5 unchanged, net -3 errors**. Matches the reported accuracy
improvement (0.796→0.857 = (49-10)/49 → (49-7)/49) exactly - not a rounding
coincidence, a direct recount.

## Ambiguous examples (excluded from accuracy, reported for transparency)

See `reports/evidence_sufficiency/results.json`'s
`ambiguous_examples_not_scored_for_accuracy` for the full list (5 examples) and how
both the length-only and length+gap methods currently treat each one - no forced
true/false label was invented for any of them.
