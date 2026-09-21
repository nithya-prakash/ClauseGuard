"""Train the baseline (TF-IDF + logistic regression) clause classifier on
train.json and save it. Run prepare_dataset.py first.

Usage:
    python training/scripts/train_baseline_classifier.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.classification.baseline import save_model, train  # noqa: E402

DATASET_DIR = ROOT / "training" / "datasets" / "clause_classification"
MODEL_PATH = ROOT / "training" / "models" / "baseline_classifier.joblib"


def main() -> None:
    train_examples = json.loads((DATASET_DIR / "train.json").read_text(encoding="utf-8"))
    pipeline = train(train_examples)
    save_model(pipeline, MODEL_PATH)
    print(f"Trained on {len(train_examples)} examples, saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
