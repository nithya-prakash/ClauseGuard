"""Baseline clause classifier: TF-IDF (word 1-2grams) + multinomial logistic
regression. This is the BASELINE the spec requires before LoRA fine-tuning
(Milestone 4) - simple and fully reproducible, not tuned for maximum
accuracy. Real comparison numbers (baseline vs LoRA) land once Milestone 4
is measured; until then any "LoRA beats baseline" claim would be
fabricated, so none is made here.
"""

from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.core.exceptions import ClassifierNotTrainedError
from app.schemas.classification import ClassificationResult
from app.services.classification.labels import CLAUSE_LABELS

MODEL_NAME = "baseline-tfidf-logreg-v1"
RANDOM_SEED = 42


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, lowercase=True),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def train(examples: list[dict[str, str]]) -> Pipeline:
    texts = [ex["text"] for ex in examples]
    labels = [ex["clause_type"] for ex in examples]
    unknown = set(labels) - set(CLAUSE_LABELS)
    if unknown:
        raise ValueError(f"Training examples contain unknown labels: {unknown}")

    pipeline = build_pipeline()
    pipeline.fit(texts, labels)
    return pipeline


def save_model(pipeline: Pipeline, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)


def load_model(path: Path) -> Pipeline:
    if not path.exists():
        raise ClassifierNotTrainedError(
            f"No trained classifier found at {path}. Run "
            "training/scripts/train_baseline_classifier.py first."
        )
    result: Pipeline = joblib.load(path)
    return result


def predict(pipeline: Pipeline, text: str) -> ClassificationResult:
    probs: Any = pipeline.predict_proba([text])[0]
    classes: Any = pipeline.classes_
    best_idx = probs.argmax()
    return ClassificationResult(
        clause_type=str(classes[best_idx]),
        confidence=round(float(probs[best_idx]), 4),
        model_name=MODEL_NAME,
    )
