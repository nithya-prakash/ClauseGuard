# Baseline classifier evaluation report

Generated: 2026-09-20T14:12:10.936617+00:00
Model: baseline-tfidf-logreg-v1 (training/models/baseline_classifier.joblib)
Dataset: training/datasets/clause_classification (synthetic, hand-authored - see dataset.json _provenance)
Test set size: 20

## Headline metrics

- Accuracy: **0.6**
- Macro precision: **0.5733**
- Macro recall: **0.6**
- Macro F1: **0.5471**

## Per-class F1

| Label | F1 |
|---|---|
| LIABILITY | 1.0 |
| TERMINATION | 0.6667 |
| PAYMENT | 0.5 |
| DATA_PROCESSING | 1.0 |
| CONFIDENTIALITY | 0.4 |
| NON_COMPETE | 0.0 |
| INTELLECTUAL_PROPERTY | 0.6667 |
| WARRANTY | 0.6667 |
| GENERAL_TERMS | 0.0 |
| OTHER | 0.5714 |

## sklearn classification_report

```
                       precision    recall  f1-score   support

            LIABILITY     1.0000    1.0000    1.0000         2
          TERMINATION     1.0000    0.5000    0.6667         2
              PAYMENT     0.5000    0.5000    0.5000         2
      DATA_PROCESSING     1.0000    1.0000    1.0000         2
      CONFIDENTIALITY     0.3333    0.5000    0.4000         2
          NON_COMPETE     0.0000    0.0000    0.0000         2
INTELLECTUAL_PROPERTY     1.0000    0.5000    0.6667         2
             WARRANTY     0.5000    1.0000    0.6667         2
        GENERAL_TERMS     0.0000    0.0000    0.0000         2
                OTHER     0.4000    1.0000    0.5714         2

             accuracy                         0.6000        20
            macro avg     0.5733    0.6000    0.5471        20
         weighted avg     0.5733    0.6000    0.5471        20

```

## Limitations

- Test set has only 2 examples per class (20 total) - metrics are high-variance at this N; a single misclassification swings a class's F1 by 0.5. Not representative of real-world contract language diversity.
- Dataset is synthetic and hand-authored by the developer, not sourced from or reviewed against real contracts.
