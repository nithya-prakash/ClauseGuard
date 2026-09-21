# Baseline vs LoRA classifier comparison

Generated: 2026-09-20T14:16:50.953151+00:00

Both rows are real measured results from `eval/classification/evaluate_baseline.py` and `eval/classification/evaluate_lora.py` on the same held-out test split (20 examples). Neither number is invented.

| Model | Accuracy | Macro precision | Macro recall | Macro F1 |
|---|---|---|---|---|
| Baseline (baseline-tfidf-logreg-v1) | 0.6 | 0.5733 | 0.6 | 0.5471 |
| LoRA (lora-distilbert-multilingual-v1) | 0.6 | 0.65 | 0.6 | 0.59 |

## Per-class F1 comparison

| Label | Baseline F1 | LoRA F1 |
|---|---|---|
| LIABILITY | 1.0 | 0.8 |
| TERMINATION | 0.6667 | 0.8 |
| PAYMENT | 0.5 | 0.4 |
| DATA_PROCESSING | 1.0 | 0.4 |
| CONFIDENTIALITY | 0.4 | 0.5 |
| NON_COMPETE | 0.0 | 0.6667 |
| INTELLECTUAL_PROPERTY | 0.6667 | 0.6667 |
| WARRANTY | 0.6667 | 0.6667 |
| GENERAL_TERMS | 0.0 | 1.0 |
| OTHER | 0.5714 | 0.0 |

## Caveat

- Both models are evaluated on a 20-example test set from a single hand-authored synthetic dataset - this comparison shows whether the LoRA pipeline works end-to-end and gives a directional signal, not a statistically robust benchmark. See each model's own report for additional limitations.
