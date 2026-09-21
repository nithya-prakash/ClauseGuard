from functools import lru_cache
from pathlib import Path

from sklearn.pipeline import Pipeline

from app.schemas.classification import ClassificationResult
from app.services.classification.baseline import load_model, predict

# Deliberately not in app/core/config.py's Settings: this is a filesystem
# artifact path, not a runtime-configurable environment setting.
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[4] / "training" / "models" / "baseline_classifier.joblib"
)


@lru_cache
def _get_pipeline(model_path: Path) -> Pipeline:
    return load_model(model_path)


def classify_clause(text: str, model_path: Path = DEFAULT_MODEL_PATH) -> ClassificationResult:
    pipeline = _get_pipeline(model_path)
    return predict(pipeline, text)
