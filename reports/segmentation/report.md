# Segmentation evaluation report

Generated: 2026-10-09T10:40:07.868491+00:00
Benchmark: data/benchmark/segmentation/contract_source.json (1 synthetic contract, hand-authored ground truth)

| File | Expected | Predicted | Exact match | Section accuracy | Heading accuracy |
|---|---|---|---|---|---|
| sample_contract_de.pdf | 10 | 10 | True | 1.0 | 1.0 |
| sample_contract_de.docx | 10 | 10 | True | 1.0 | 1.0 |

## Limitations

- Single benchmark document - measures correctness on one contract structure, not generalization across real-world contract styles.
- Ground truth is authored, not independently reviewed by a legal expert (no real contract or legal labeling involved).
