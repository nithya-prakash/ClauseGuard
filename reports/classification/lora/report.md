# LoRA classifier evaluation report

Generated: 2026-09-20T14:16:50.920381+00:00
Model: lora-distilbert-multilingual-v1 (base: distilbert-base-multilingual-cased)
Adapter: training/adapter/clause_classifier
Test set size: 20

## Headline metrics

- Accuracy: **0.6**
- Macro precision: **0.65**
- Macro recall: **0.6**
- Macro F1: **0.59**

## Per-class F1

| Label | F1 |
|---|---|
| LIABILITY | 0.8 |
| TERMINATION | 0.8 |
| PAYMENT | 0.4 |
| DATA_PROCESSING | 0.4 |
| CONFIDENTIALITY | 0.5 |
| NON_COMPETE | 0.6667 |
| INTELLECTUAL_PROPERTY | 0.6667 |
| WARRANTY | 0.6667 |
| GENERAL_TERMS | 1.0 |
| OTHER | 0.0 |

## sklearn classification_report

```
                       precision    recall  f1-score   support

            LIABILITY     0.6667    1.0000    0.8000         2
          TERMINATION     0.6667    1.0000    0.8000         2
              PAYMENT     0.3333    0.5000    0.4000         2
      DATA_PROCESSING     0.3333    0.5000    0.4000         2
      CONFIDENTIALITY     0.5000    0.5000    0.5000         2
          NON_COMPETE     1.0000    0.5000    0.6667         2
INTELLECTUAL_PROPERTY     1.0000    0.5000    0.6667         2
             WARRANTY     1.0000    0.5000    0.6667         2
        GENERAL_TERMS     1.0000    1.0000    1.0000         2
                OTHER     0.0000    0.0000    0.0000         2

             accuracy                         0.6000        20
            macro avg     0.6500    0.6000    0.5900        20
         weighted avg     0.6500    0.6000    0.5900        20

```

## Limitations

- Test set has only 2 examples per class (20 total) - metrics are high-variance at this N.
- Dataset is synthetic and hand-authored, not sourced from or reviewed against real contracts.
- Trained for 12 epochs on 80 examples - a demonstration of a working LoRA pipeline, not a production-scale fine-tune.
