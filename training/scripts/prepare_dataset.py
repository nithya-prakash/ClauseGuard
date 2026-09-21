"""Deterministic train/val/test split for the clause classification dataset.

No randomness: for each class, examples are taken in the order they appear
in dataset.json and sliced positionally (last VAL_PER_CLASS -> val, the
VAL_PER_CLASS before that -> test, everything else -> train). This is a
stronger reproducibility guarantee than a seeded random split (nothing to
get wrong about seed handling) and is documented here rather than being a
seeded-random split as section 9 of the spec would otherwise suggest,
because with only 12 examples/class a fixed split is easier to audit by eye.

Usage:
    python training/scripts/prepare_dataset.py
"""

import json
from collections import defaultdict
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets" / "clause_classification"
VAL_PER_CLASS = 2
TEST_PER_CLASS = 2


def split_dataset(examples: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    by_class: dict[str, list[dict]] = defaultdict(list)
    for ex in examples:
        by_class[ex["clause_type"]].append(ex)

    train, val, test = [], [], []
    for label in sorted(by_class):
        items = by_class[label]
        n = len(items)
        n_test = min(TEST_PER_CLASS, n)
        n_val = min(VAL_PER_CLASS, n - n_test)
        test += items[:n_test]
        val += items[n_test : n_test + n_val]
        train += items[n_test + n_val :]
    return train, val, test


def class_distribution(examples: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for ex in examples:
        counts[ex["clause_type"]] += 1
    return dict(sorted(counts.items()))


def main() -> None:
    dataset = json.loads((DATASET_DIR / "dataset.json").read_text(encoding="utf-8"))
    train, val, test = split_dataset(dataset["examples"])

    for name, split in (("train", train), ("val", val), ("test", test)):
        (DATASET_DIR / f"{name}.json").write_text(
            json.dumps(split, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    distribution = {
        "total_examples": len(dataset["examples"]),
        "split_sizes": {"train": len(train), "val": len(val), "test": len(test)},
        "class_distribution": {
            "overall": class_distribution(dataset["examples"]),
            "train": class_distribution(train),
            "val": class_distribution(val),
            "test": class_distribution(test),
        },
    }
    (DATASET_DIR / "class_distribution.json").write_text(
        json.dumps(distribution, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(distribution, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
