"""Evaluate the trained baseline classifier on the held-out test split.

Every number in reports/classification/baseline/{results.json,report.md} is
computed here from actually running the model - nothing is hand-typed.
Run prepare_dataset.py and train_baseline_classifier.py first.

Usage:
    python eval/classification/evaluate_baseline.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.classification.baseline import MODEL_NAME, load_model, predict  # noqa: E402
from app.services.classification.labels import CLAUSE_LABELS  # noqa: E402

DATASET_DIR = ROOT / "training" / "datasets" / "clause_classification"
MODEL_PATH = ROOT / "training" / "models" / "baseline_classifier.joblib"
REPORT_DIR = ROOT / "reports" / "classification" / "baseline"


def main() -> None:
    test_examples = json.loads((DATASET_DIR / "test.json").read_text(encoding="utf-8"))
    pipeline = load_model(MODEL_PATH)

    y_true = [ex["clause_type"] for ex in test_examples]
    y_pred = [predict(pipeline, ex["text"]).clause_type for ex in test_examples]

    accuracy = sum(t == p for t, p in zip(y_true, y_pred, strict=True)) / len(y_true)
    common = {"labels": CLAUSE_LABELS, "zero_division": 0}
    macro_precision = precision_score(y_true, y_pred, average="macro", **common)
    macro_recall = recall_score(y_true, y_pred, average="macro", **common)
    macro_f1 = f1_score(y_true, y_pred, average="macro", **common)
    per_class_f1 = f1_score(y_true, y_pred, average=None, **common)
    cm = confusion_matrix(y_true, y_pred, labels=CLAUSE_LABELS)
    text_report = classification_report(
        y_true, y_pred, labels=CLAUSE_LABELS, zero_division=0, digits=4
    )

    output = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "model_name": MODEL_NAME,
        "model_path": str(MODEL_PATH.relative_to(ROOT)),
        "dataset": (
            "training/datasets/clause_classification "
            "(synthetic, hand-authored - see dataset.json _provenance)"
        ),
        "test_set_size": len(test_examples),
        "accuracy": round(accuracy, 4),
        "macro_precision": round(float(macro_precision), 4),
        "macro_recall": round(float(macro_recall), 4),
        "macro_f1": round(float(macro_f1), 4),
        "per_class_f1": {
            label: round(float(score), 4)
            for label, score in zip(CLAUSE_LABELS, per_class_f1, strict=True)
        },
        "confusion_matrix": {"labels": CLAUSE_LABELS, "matrix": cm.tolist()},
        "limitations": [
            "Test set has only 2 examples per class (20 total) - metrics are "
            "high-variance at this N; a single misclassification swings a "
            "class's F1 by 0.5. Not representative of real-world contract "
            "language diversity.",
            "Dataset is synthetic and hand-authored by the developer, not "
            "sourced from or reviewed against real contracts.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Baseline classifier evaluation report",
        "",
        f"Generated: {output['evaluated_at']}",
        f"Model: {output['model_name']} ({output['model_path']})",
        f"Dataset: {output['dataset']}",
        f"Test set size: {output['test_set_size']}",
        "",
        "## Headline metrics",
        "",
        f"- Accuracy: **{output['accuracy']}**",
        f"- Macro precision: **{output['macro_precision']}**",
        f"- Macro recall: **{output['macro_recall']}**",
        f"- Macro F1: **{output['macro_f1']}**",
        "",
        "## Per-class F1",
        "",
        "| Label | F1 |",
        "|---|---|",
    ]
    for label, score in output["per_class_f1"].items():
        lines.append(f"| {label} | {score} |")
    lines += [
        "",
        "## sklearn classification_report",
        "",
        "```",
        text_report,
        "```",
        "",
        "## Limitations",
        "",
    ]
    lines += [f"- {limitation}" for limitation in output["limitations"]]
    (REPORT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
