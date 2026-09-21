"""Train the LoRA-adapted clause classifier.

Manual PyTorch training loop (not HF Trainer) for full control and no
external logging integrations. Deterministic: fixed seed for model init,
data-loader shuffling, and everything else torch.manual_seed reaches.
Run prepare_dataset.py first.

Usage:
    python training/scripts/train_lora_classifier.py
"""

import json
import sys
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.classification.lora_classifier import (  # noqa: E402
    LABEL2ID,
    build_lora_model,
    get_device,
    load_config,
    load_tokenizer,
)

CONFIG_PATH = ROOT / "training" / "configs" / "lora_classifier.json"
DATASET_DIR = ROOT / "training" / "datasets" / "clause_classification"
ADAPTER_DIR = ROOT / "training" / "adapter" / "clause_classifier"


class ClauseDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(self, examples: list[dict[str, str]], tokenizer: Any, max_length: int):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        ex = self.examples[idx]
        enc = self.tokenizer(
            ex["text"],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(LABEL2ID[ex["clause_type"]], dtype=torch.long)
        return item


def main() -> None:
    config = load_config(CONFIG_PATH)
    seed = config["training"]["seed"]
    torch.manual_seed(seed)

    device = get_device()
    print(f"Training on device: {device}")

    tokenizer = load_tokenizer(config["base_model"])
    model = build_lora_model(config["base_model"], config["lora"]).to(device)
    model.print_trainable_parameters()

    train_examples = json.loads((DATASET_DIR / "train.json").read_text(encoding="utf-8"))
    val_examples = json.loads((DATASET_DIR / "val.json").read_text(encoding="utf-8"))

    train_ds = ClauseDataset(train_examples, tokenizer, config["max_seq_length"])
    val_ds = ClauseDataset(val_examples, tokenizer, config["max_seq_length"])

    train_loader = DataLoader(
        train_ds,
        batch_size=config["training"]["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    val_loader = DataLoader(val_ds, batch_size=config["training"]["batch_size"])

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=config["training"]["learning_rate"],
        weight_decay=config["training"]["weight_decay"],
    )

    history = []
    for epoch in range(1, config["training"]["epochs"] + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        train_loss = total_loss / len(train_loader)

        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                outputs = model(**batch)
                preds = outputs.logits.argmax(dim=-1)
                val_correct += int((preds == batch["labels"]).sum().item())
                val_total += len(batch["labels"])
        val_acc = val_correct / val_total if val_total else 0.0
        history.append(
            {"epoch": epoch, "train_loss": round(train_loss, 4), "val_accuracy": round(val_acc, 4)}
        )
        print(f"epoch {epoch}: train_loss={train_loss:.4f} val_acc={val_acc:.4f}")

    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ADAPTER_DIR))
    (ADAPTER_DIR / "training_history.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    print(f"Saved adapter to {ADAPTER_DIR}")


if __name__ == "__main__":
    main()
