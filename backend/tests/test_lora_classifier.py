from pathlib import Path

import pytest

from app.core.exceptions import ClassifierNotTrainedError
from app.services.classification.labels import CLAUSE_LABELS
from app.services.classification.lora_classifier import (
    get_device,
    load_config,
    load_tokenizer,
    load_trained,
    predict,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "training" / "configs" / "lora_classifier.json"
ADAPTER_DIR = REPO_ROOT / "training" / "adapter" / "clause_classifier"


def test_load_trained_missing_adapter_raises(tmp_path: Path):
    # No network/model download involved: load_trained checks the adapter
    # path exists before touching the base model.
    with pytest.raises(ClassifierNotTrainedError):
        load_trained(tmp_path / "does_not_exist", "distilbert-base-multilingual-cased")


@pytest.mark.integration
def test_real_trained_adapter_predicts_valid_label():
    # Requires training/scripts/train_lora_classifier.py to have been run
    # (downloads the base model on first use) - not run in default CI.
    config = load_config(CONFIG_PATH)
    device = get_device()
    tokenizer = load_tokenizer(config["base_model"])
    model = load_trained(ADAPTER_DIR, config["base_model"]).to(device)

    result = predict(
        model,
        tokenizer,
        "Der Auftragnehmer haftet nur für Vorsatz und grobe Fahrlässigkeit.",
        device,
    )
    assert result.clause_type in CLAUSE_LABELS
    assert 0.0 <= result.confidence <= 1.0
