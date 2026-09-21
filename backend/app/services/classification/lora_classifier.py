"""LoRA-adapted clause classifier: a small multilingual encoder
(distilbert-base-multilingual-cased, see training/configs/lora_classifier.json
for the model-choice rationale) with a sequence-classification head, tuned
via PEFT/LoRA. Mirrors baseline.py's load/predict interface so the two are
interchangeable from the caller's perspective.
"""

import json
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedTokenizerBase

from app.core.exceptions import ClassifierNotTrainedError
from app.schemas.classification import ClassificationResult
from app.services.classification.labels import CLAUSE_LABELS

MODEL_NAME = "lora-distilbert-multilingual-v1"
LABEL2ID = {label: i for i, label in enumerate(CLAUSE_LABELS)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}


def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_config(config_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    return result


def build_base_model(base_model_name: str) -> Any:
    return AutoModelForSequenceClassification.from_pretrained(
        base_model_name,
        num_labels=len(CLAUSE_LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )


def build_lora_model(base_model_name: str, lora_cfg: dict[str, Any]) -> Any:
    base = build_base_model(base_model_name)
    peft_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["alpha"],
        lora_dropout=lora_cfg["dropout"],
        target_modules=lora_cfg["target_modules"],
    )
    return get_peft_model(base, peft_config)


def load_tokenizer(base_model_name: str) -> PreTrainedTokenizerBase:
    result: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(base_model_name)
    return result


def load_trained(adapter_path: Path, base_model_name: str) -> Any:
    if not adapter_path.exists():
        raise ClassifierNotTrainedError(
            f"No trained LoRA adapter found at {adapter_path}. Run "
            "training/scripts/train_lora_classifier.py first."
        )
    base = build_base_model(base_model_name)
    model = PeftModel.from_pretrained(base, str(adapter_path))
    model.eval()
    return model


def predict(
    model: Any, tokenizer: PreTrainedTokenizerBase, text: str, device: torch.device
) -> ClassificationResult:
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128).to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
    best_id = int(torch.argmax(probs).item())
    return ClassificationResult(
        clause_type=ID2LABEL[best_id],
        confidence=round(float(probs[best_id]), 4),
        model_name=MODEL_NAME,
    )
