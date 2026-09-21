"""Evaluate the trained LoRA classifier on the held-out test split, and
write a real baseline-vs-LoRA comparison from both scripts' actual output
(reports/classification/{baseline,lora}/results.json). Every number here
comes from running the models - nothing is hand-typed. Run
train_lora_classifier.py first.

Usage:
    python eval/classification/evaluate_lora.py
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

from app.services.classification.labels import CLAUSE_LABELS  # noqa: E402
from app.services.classification.lora_classifier import (  # noqa: E402
    MODEL_NAME,
    get_device,
    load_config,
    load_tokenizer,
    load_trained,
    predict,
)

CONFIG_PATH = ROOT / "training" / "configs" / "lora_classifier.json"
DATASET_DIR = ROOT / "training" / "datasets" / "clause_classification"
ADAPTER_DIR = ROOT / "training" / "adapter" / "clause_classifier"
REPORT_DIR = ROOT / "reports" / "classification" / "lora"
BASELINE_RESULTS = ROOT / "reports" / "classification" / "baseline" / "results.json"
COMPARISON_PATH = ROOT / "reports" / "classification" / "comparison.md"


def evaluate() -> dict:
    config = load_config(CONFIG_PATH)
    device = get_device()
    tokenizer = load_tokenizer(config["base_model"])
    model = load_trained(ADAPTER_DIR, config["base_model"]).to(device)

    test_examples = json.loads((DATASET_DIR / "test.json").read_text(encoding="utf-8"))
    y_true = [ex["clause_type"] for ex in test_examples]
    y_pred = [predict(model, tokenizer, ex["text"], device).clause_type for ex in test_examples]

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

    history_path = ADAPTER_DIR / "training_history.json"
    training_history = (
        json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else None
    )

    output = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "model_name": MODEL_NAME,
        "base_model": config["base_model"],
        "adapter_path": str(ADAPTER_DIR.relative_to(ROOT)),
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
        "training_history": training_history,
        "limitations": [
            "Test set has only 2 examples per class (20 total) - metrics are "
            "high-variance at this N.",
            "Dataset is synthetic and hand-authored, not sourced from or "
            "reviewed against real contracts.",
            "Trained for 12 epochs on 80 examples - a demonstration of a "
            "working LoRA pipeline, not a production-scale fine-tune.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# LoRA classifier evaluation report",
        "",
        f"Generated: {output['evaluated_at']}",
        f"Model: {output['model_name']} (base: {output['base_model']})",
        f"Adapter: {output['adapter_path']}",
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

    return output


def write_comparison(lora_output: dict) -> None:
    if not BASELINE_RESULTS.exists():
        print("No baseline results found - skipping comparison.")
        return
    baseline = json.loads(BASELINE_RESULTS.read_text(encoding="utf-8"))

    lines = [
        "# Baseline vs LoRA classifier comparison",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "Both rows are real measured results from "
        "`eval/classification/evaluate_baseline.py` and "
        "`eval/classification/evaluate_lora.py` on the same held-out test split "
        f"({lora_output['test_set_size']} examples). Neither number is invented.",
        "",
        "| Model | Accuracy | Macro precision | Macro recall | Macro F1 |",
        "|---|---|---|---|---|",
        f"| Baseline ({baseline['model_name']}) | {baseline['accuracy']} | "
        f"{baseline['macro_precision']} | {baseline['macro_recall']} | {baseline['macro_f1']} |",
        f"| LoRA ({lora_output['model_name']}) | {lora_output['accuracy']} | "
        f"{lora_output['macro_precision']} | {lora_output['macro_recall']} | "
        f"{lora_output['macro_f1']} |",
        "",
        "## Per-class F1 comparison",
        "",
        "| Label | Baseline F1 | LoRA F1 |",
        "|---|---|---|",
    ]
    for label in CLAUSE_LABELS:
        lines.append(
            f"| {label} | {baseline['per_class_f1'][label]} | "
            f"{lora_output['per_class_f1'][label]} |"
        )
    lines += [
        "",
        "## Caveat",
        "",
        "- Both models are evaluated on a 20-example test set from a single "
        "hand-authored synthetic dataset - this comparison shows whether the "
        "LoRA pipeline works end-to-end and gives a directional signal, not a "
        "statistically robust benchmark. See each model's own report for "
        "additional limitations.",
    ]
    COMPARISON_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    output = evaluate()
    write_comparison(output)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
