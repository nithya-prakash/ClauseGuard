"""Segmentation evaluation against the manually-authored benchmark contract.

Runs the REAL ingestion + segmentation pipeline (no mocks) against the
synthetic fixtures in data/benchmark/segmentation/ and compares the result to
ground_truth.json. Writes reports/segmentation/results.json (machine-readable)
and reports/segmentation/report.md (human-readable). Every number in those
two files comes from actually running the pipeline below - nothing is typed
in by hand.

This benchmark has exactly one document (by construction, since it's hand
authored ground truth) - that is a real limitation, documented in the report,
not hidden. It answers "does the segmenter work correctly on a document with
this structure", not "how well does it generalize across contract styles".

Usage:
    python eval/segmentation/evaluate_segmentation.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ingestion.service import ingest_document  # noqa: E402
from app.services.segmentation.segmenter import segment_document  # noqa: E402

BENCHMARK_DIR = ROOT / "data" / "benchmark" / "segmentation"
REPORT_DIR = ROOT / "reports" / "segmentation"


def evaluate_file(path: Path, ground_truth: dict) -> dict:
    document = ingest_document(path)
    predicted = segment_document(document)
    expected = ground_truth["clauses"]

    section_matches = 0
    heading_matches = 0
    for i, exp in enumerate(expected):
        if i >= len(predicted):
            continue
        pred = predicted[i]
        if pred.section == exp["section"]:
            section_matches += 1
        if (pred.heading or "").strip() == exp["heading"].strip():
            heading_matches += 1

    n_expected = len(expected)
    return {
        "file": path.name,
        "expected_clause_count": n_expected,
        "predicted_clause_count": len(predicted),
        "clause_count_exact_match": len(predicted) == n_expected,
        "section_label_accuracy": round(section_matches / n_expected, 4) if n_expected else None,
        "heading_accuracy": round(heading_matches / n_expected, 4) if n_expected else None,
        "pagination_available": document.pagination_available,
    }


def main() -> None:
    ground_truth = json.loads((BENCHMARK_DIR / "ground_truth.json").read_text(encoding="utf-8"))

    results = [
        evaluate_file(BENCHMARK_DIR / "sample_contract_de.pdf", ground_truth),
        evaluate_file(BENCHMARK_DIR / "sample_contract_de.docx", ground_truth),
    ]

    output = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "benchmark": (
            "data/benchmark/segmentation/contract_source.json "
            "(1 synthetic contract, hand-authored ground truth)"
        ),
        "script": "eval/segmentation/evaluate_segmentation.py",
        "limitations": [
            "Single benchmark document - measures correctness on one contract "
            "structure, not generalization across real-world contract styles.",
            "Ground truth is authored, not independently reviewed by a legal expert "
            "(no real contract or legal labeling involved).",
        ],
        "results": results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Segmentation evaluation report",
        "",
        f"Generated: {output['evaluated_at']}",
        f"Benchmark: {output['benchmark']}",
        "",
        "| File | Expected | Predicted | Exact match | Section accuracy | Heading accuracy |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['file']} | {r['expected_clause_count']} | {r['predicted_clause_count']} | "
            f"{r['clause_count_exact_match']} | {r['section_label_accuracy']} | "
            f"{r['heading_accuracy']} |"
        )
    lines += ["", "## Limitations", ""]
    lines += [f"- {limitation}" for limitation in output["limitations"]]
    (REPORT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
