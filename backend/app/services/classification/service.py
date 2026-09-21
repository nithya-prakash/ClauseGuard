from functools import lru_cache
from pathlib import Path
from typing import Any

from sklearn.pipeline import Pipeline

from app.schemas.classification import ClassificationResult
from app.services.classification import lora_classifier
from app.services.classification.baseline import load_model, predict

# Deliberately not in app/core/config.py's Settings: these are filesystem
# artifact paths, not runtime-configurable environment settings.
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[4] / "training" / "models" / "baseline_classifier.joblib"
)
DEFAULT_LORA_ADAPTER_PATH = (
    Path(__file__).resolve().parents[4] / "training" / "adapter" / "clause_classifier"
)
DEFAULT_LORA_CONFIG_PATH = (
    Path(__file__).resolve().parents[4] / "training" / "configs" / "lora_classifier.json"
)


@lru_cache
def _get_pipeline(model_path: Path) -> Pipeline:
    return load_model(model_path)


def classify_clause(text: str, model_path: Path = DEFAULT_MODEL_PATH) -> ClassificationResult:
    """Baseline (TF-IDF + logistic regression) classification."""
    pipeline = _get_pipeline(model_path)
    return predict(pipeline, text)


@lru_cache
def _get_lora_model_and_tokenizer(
    adapter_path: Path, config_path: Path
) -> tuple[Any, Any]:
    config = lora_classifier.load_config(config_path)
    tokenizer = lora_classifier.load_tokenizer(config["base_model"])
    device = lora_classifier.get_device()
    model = lora_classifier.load_trained(adapter_path, config["base_model"]).to(device)
    return model, tokenizer


def classify_clause_lora(
    text: str,
    adapter_path: Path = DEFAULT_LORA_ADAPTER_PATH,
    config_path: Path = DEFAULT_LORA_CONFIG_PATH,
) -> ClassificationResult:
    """LoRA-fine-tuned classification (Milestone 4) - measured better than
    the baseline (macro F1 0.59 vs 0.547, see reports/classification/
    comparison.md), so the end-to-end pipeline (Milestone 10) uses this by
    default, falling back to the baseline only if no adapter is trained in
    this environment (see pipeline/document_analysis.py)."""
    model, tokenizer = _get_lora_model_and_tokenizer(adapter_path, config_path)
    device = lora_classifier.get_device()
    return lora_classifier.predict(model, tokenizer, text, device)
