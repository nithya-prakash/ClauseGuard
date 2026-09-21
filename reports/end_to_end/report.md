# End-to-end pipeline evaluation report

Generated: 2026-09-20T15:24:23.325115+00:00
Contract: data/benchmark/segmentation/sample_contract_de.pdf (10 clauses)

## Component results

- Segmentation: 10/10 clauses detected (PASS)
- Classification accuracy: **0.8** (0 failures)
- Evidence sufficiency accuracy: **0.3** (10 conclusive / 0 inconclusive)
- Reasoning: **NOT_MEASURED** (no ANTHROPIC_API_KEY; 9 clauses would have reached the LLM)
- Citation verification: **NOT_MEASURED** (depends on reasoning)
- Report generation: **NOT_APPLICABLE** (Milestone 13 not yet built)

## Per-clause detail

| § | Expected type | Predicted type | Class. OK | Corpus covered | Sufficient? |
|---|---|---|---|---|---|
| § 1 | GENERAL_TERMS | PAYMENT | False | False | True |
| § 2 | PAYMENT | PAYMENT | True | False | True |
| § 3 | TERMINATION | TERMINATION | True | True | True |
| § 4 | LIABILITY | NON_COMPETE | False | True | True |
| § 5 | WARRANTY | WARRANTY | True | False | True |
| § 6 | CONFIDENTIALITY | CONFIDENTIALITY | True | False | True |
| § 7 | DATA_PROCESSING | DATA_PROCESSING | True | True | True |
| § 8 | NON_COMPETE | NON_COMPETE | True | False | True |
| § 9 | INTELLECTUAL_PROPERTY | INTELLECTUAL_PROPERTY | True | False | True |
| § 10 | GENERAL_TERMS | GENERAL_TERMS | True | True | False |

## Limitations

- Single benchmark contract (10 clauses) - measures whether the wired pipeline behaves correctly, not statistically robust component accuracy.
- Reasoning/citation-verification quality genuinely not measured (no LLM call made), not omitted for convenience.
