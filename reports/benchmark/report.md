# Multi-contract benchmark report

Generated: 2026-10-09T10:27:23.806250+00:00
5 contracts, 63 labelled clauses (original 10-clause contract plus 4 new synthetic contracts). Real pipeline, no mocks. Raw output: `results.json`.

| Metric | LoRA (pipeline default) | TF-IDF baseline |
|---|---|---|
| Accuracy (95% Wilson CI) | 0.556 [0.433, 0.672] | 0.619 [0.496, 0.729] |
| Macro F1 | 0.546 | 0.632 |
| Accuracy excluding 10 clauses overlapping the training set | 0.528 | 0.566 |

- Evidence sufficiency vs corpus-coverage labels: **0.794** [0.678, 0.875] on 63 clauses (22 labelled covered).
- Segmentation: exact section match on 4 of 5 contracts.
- Training overlap: 10 clauses exceed 0.6 similarity to a training clause (max 0.888, mean of max 0.407).
- Reasoning and citation verification: NOT_MEASURED (no Anthropic key).

## Reading

The LoRA classifier does not beat the TF-IDF baseline here; the earlier 0.59 vs 0.547 macro-F1 gap on 20 examples does not hold on 63 clauses, and the intervals overlap heavily. Segmentation fails on `kaufvertrag_maschine`: a wrapped line beginning '50 Prozent ...' is read as a numbered heading and splits clause § 2.

## Limitations

- Contracts and labels were written by the same person who built the system, after seeing the 10 classes; they are not independently reviewed.
- 63 clauses is still small: confidence intervals above are wide.
- corpus_covered is a judgment against 15 passages; reasoning quality is not measured (no Anthropic key).
