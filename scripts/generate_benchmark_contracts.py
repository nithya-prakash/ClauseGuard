"""Render the PDF contracts for the multi-contract benchmark from
data/benchmark/contracts/contracts_source.json (one PDF per contract).

Usage:
    python scripts/generate_benchmark_contracts.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_benchmark_fixtures import generate_pdf  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "benchmark" / "contracts"


def main() -> None:
    source = json.loads((OUT_DIR / "contracts_source.json").read_text(encoding="utf-8"))
    for contract in source["contracts"]:
        generate_pdf(contract, OUT_DIR / f"{contract['id']}.pdf")
    print(f"Wrote {len(source['contracts'])} PDFs to {OUT_DIR}")


if __name__ == "__main__":
    main()
