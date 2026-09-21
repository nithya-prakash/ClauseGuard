import json
from pathlib import Path

import pytest

from app.core.exceptions import ClassifierNotTrainedError
from app.services.classification import baseline
from app.services.classification.labels import CLAUSE_LABELS
from app.services.classification.service import classify_clause

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = REPO_ROOT / "training" / "datasets" / "clause_classification" / "train.json"


def _train_examples() -> list[dict[str, str]]:
    return json.loads(TRAIN_PATH.read_text(encoding="utf-8"))


def test_train_produces_valid_predictions():
    pipeline = baseline.train(_train_examples())
    result = baseline.predict(
        pipeline,
        "Der Auftragnehmer verarbeitet personenbezogene Daten gemäß Art. 28 DSGVO.",
    )
    assert result.clause_type in CLAUSE_LABELS
    assert 0.0 <= result.confidence <= 1.0
    assert result.model_name == baseline.MODEL_NAME


def test_train_rejects_unknown_labels():
    with pytest.raises(ValueError, match="unknown labels"):
        baseline.train([{"text": "irrelevant", "clause_type": "NOT_A_REAL_LABEL"}])


def test_load_model_missing_raises_classifier_not_trained_error(tmp_path: Path):
    with pytest.raises(ClassifierNotTrainedError):
        baseline.load_model(tmp_path / "does_not_exist.joblib")


def test_save_and_load_model_roundtrip(tmp_path: Path):
    pipeline = baseline.train(_train_examples())
    model_path = tmp_path / "model.joblib"
    baseline.save_model(pipeline, model_path)

    loaded = baseline.load_model(model_path)
    result = baseline.predict(loaded, "Die Miete ist monatlich im Voraus zu entrichten.")
    assert result.clause_type in CLAUSE_LABELS


def test_service_classify_clause_end_to_end(tmp_path: Path):
    pipeline = baseline.train(_train_examples())
    model_path = tmp_path / "service_model.joblib"
    baseline.save_model(pipeline, model_path)

    result = classify_clause(
        "Der Vertrag kann mit einer Frist von drei Monaten gekündigt werden.",
        model_path=model_path,
    )
    assert result.clause_type in CLAUSE_LABELS


def test_service_classify_clause_missing_model_raises(tmp_path: Path):
    with pytest.raises(ClassifierNotTrainedError):
        classify_clause("irrelevant text", model_path=tmp_path / "missing.joblib")
