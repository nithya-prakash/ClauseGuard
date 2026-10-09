"""Multi-contract benchmark: segmentation, classification and evidence-sufficiency on 5 contracts.

Contracts: the original 10-clause sample contract plus the 4 contracts in
data/benchmark/contracts/ (63 labelled clauses in total). Runs the real pipeline
(`analyze_document`) on each PDF and compares against the hand-authored labels. Labels are by the
same author who built the system; see the report's limitations. Also checks for text overlap
between benchmark clauses and the classifier's 120-example training set.

Usage:
    QDRANT_URL=http://localhost:6339 python eval/benchmark/evaluate_benchmark.py
"""

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.classification.labels import CLAUSE_LABELS  # noqa: E402
from app.services.classification.service import classify_clause  # noqa: E402
from app.services.pipeline.document_analysis import analyze_document  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "benchmark" / "contracts"
ORIGINAL_GT = ROOT / "data" / "benchmark" / "end_to_end" / "ground_truth.json"
TRAIN_DIR = ROOT / "training" / "datasets" / "clause_classification"
REPORT_DIR = ROOT / "reports" / "benchmark"
OVERLAP_THRESHOLD = 0.6


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    """95% Wilson interval for a proportion."""
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(centre - half, 3), round(centre + half, 3)]


def load_contracts() -> list[dict]:
    """Each contract: id, pdf path, clauses with clause_type/corpus_covered labels."""
    contracts = []
    original = json.loads(ORIGINAL_GT.read_text(encoding="utf-8"))
    contracts.append(
        {
            "id": "original_dienstleistungsvertrag",
            "pdf": ROOT / original["contract"],
            "clauses": [
                {
                    "section": c["section"],
                    "clause_type": c["expected_clause_type"],
                    "corpus_covered": c["corpus_covered"],
                }
                for c in original["clauses"]
            ],
        }
    )
    source = json.loads((CONTRACTS_DIR / "contracts_source.json").read_text(encoding="utf-8"))
    for c in source["contracts"]:
        pdf = CONTRACTS_DIR / f"{c['id']}.pdf"
        contracts.append({"id": c["id"], "pdf": pdf, "clauses": c["clauses"]})
    return contracts


def sufficiency_signal(reasoning_status: str | None, reasoning_error: str | None) -> bool | None:
    """True = judged sufficient, False = insufficient, None = inconclusive (pipeline failure)."""
    if reasoning_status == "INSUFFICIENT_EVIDENCE":
        return False
    if reasoning_error and "ANTHROPIC_API_KEY" in reasoning_error:
        return True
    return None


def overlap_with_training(texts: list[str]) -> list[float]:
    train = json.loads((TRAIN_DIR / "dataset.json").read_text(encoding="utf-8"))["examples"]
    train_texts = [e["text"] for e in train]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit(train_texts + texts)
    sims = cosine_similarity(vec.transform(texts), vec.transform(train_texts))
    return [round(float(s.max()), 3) for s in sims]


def main() -> None:
    client = QdrantClient(url=get_settings().qdrant_url)
    rows, seg_rows = [], []
    for contract in load_contracts():
        result = analyze_document(contract["pdf"], client)
        labels = contract["clauses"]
        seg_ok = result.clause_count == len(labels) and all(
            ca.clause.section == lab["section"]
            for ca, lab in zip(result.clauses, labels, strict=False)
        )
        seg_rows.append(
            {
                "contract": contract["id"],
                "expected": len(labels),
                "predicted": result.clause_count,
                "sections_match": seg_ok,
            }
        )
        # Match by section label so one spurious segment cannot shift every later clause.
        by_section = {ca.clause.section: ca for ca in result.clauses}
        for lab in labels:
            ca = by_section.get(lab["section"])
            if ca is None:
                continue
            lora = ca.classification.clause_type if ca.classification else None
            suff = sufficiency_signal(
                ca.reasoning.status if ca.reasoning else None, ca.reasoning_error
            )
            rows.append(
                {
                    "contract": contract["id"],
                    "section": lab["section"],
                    "text": ca.clause.text,
                    "expected_type": lab["clause_type"],
                    "lora_type": lora,
                    "baseline_type": classify_clause(ca.clause.text).clause_type,
                    "expected_covered": lab["corpus_covered"],
                    "sufficient": suff,
                }
            )

    n = len(rows)
    missing = sum(len(c["clauses"]) for c in load_contracts()) - n
    y = [r["expected_type"] for r in rows]
    summary: dict = {
        "contracts": len(seg_rows),
        "clauses": n,
        "labelled_clauses_not_found_by_segmenter": missing,
    }
    for name, key in (("lora", "lora_type"), ("baseline", "baseline_type")):
        pred = [r[key] for r in rows]
        k = sum(a == b for a, b in zip(y, pred, strict=True))
        summary[name] = {
            "accuracy": round(k / n, 3),
            "accuracy_ci95": wilson(k, n),
            "macro_f1": round(
                float(f1_score(y, pred, labels=CLAUSE_LABELS, average="macro", zero_division=0)), 3
            ),
            "per_class_f1": {
                lab: round(float(s), 3)
                for lab, s in zip(
                    CLAUSE_LABELS,
                    f1_score(y, pred, labels=CLAUSE_LABELS, average=None, zero_division=0),
                    strict=True,
                )
            },
        }
    conclusive = [r for r in rows if r["sufficient"] is not None]
    k = sum(r["sufficient"] == r["expected_covered"] for r in conclusive)
    summary["evidence_sufficiency"] = {
        "accuracy": round(k / len(conclusive), 3),
        "accuracy_ci95": wilson(k, len(conclusive)),
        "conclusive": len(conclusive),
        "inconclusive": n - len(conclusive),
        "covered_clauses": sum(r["expected_covered"] for r in rows),
    }
    summary["segmentation"] = {
        "contracts_exact": sum(s["sections_match"] for s in seg_rows),
        "of": len(seg_rows),
    }
    overlap = overlap_with_training([r["text"] for r in rows])
    summary["training_overlap"] = {
        "method": "max cosine similarity of char 3-5-gram TF-IDF vs the 120 training clauses",
        "threshold": OVERLAP_THRESHOLD,
        "clauses_over_threshold": sum(o > OVERLAP_THRESHOLD for o in overlap),
        "max_similarity": max(overlap),
        "mean_max_similarity": round(sum(overlap) / len(overlap), 3),
    }
    low = [r for r, o in zip(rows, overlap, strict=True) if o <= OVERLAP_THRESHOLD]
    summary["excluding_high_overlap_clauses"] = {
        "clauses": len(low),
        **{
            f"{name}_accuracy": round(sum(r[key] == r["expected_type"] for r in low) / len(low), 3)
            for name, key in (("lora", "lora_type"), ("baseline", "baseline_type"))
        },
    }
    summary["label_counts"] = {lab: y.count(lab) for lab in CLAUSE_LABELS}

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "segmentation": seg_rows,
        "per_clause": [{k: v for k, v in r.items() if k != "text"} for r in rows],
        "limitations": [
            "Contracts and labels were written by the same person who built the system, "
            "after seeing the 10 classes; they are not independently reviewed.",
            "63 clauses is still small: confidence intervals above are wide.",
            "corpus_covered is a judgment against 15 passages; reasoning quality is not "
            "measured (no Anthropic key).",
        ],
    }
    (REPORT_DIR / "results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lo, ba, ev = summary["lora"], summary["baseline"], summary["evidence_sufficiency"]
    ov, hi = summary["training_overlap"], summary["excluding_high_overlap_clauses"]
    lines = [
        "# Multi-contract benchmark report",
        "",
        f"Generated: {out['evaluated_at']}",
        f"{summary['contracts']} contracts, {n} labelled clauses (original 10-clause contract plus "
        "4 new synthetic contracts). Real pipeline, no mocks. Raw output: `results.json`.",
        "",
        "| Metric | LoRA (pipeline default) | TF-IDF baseline |",
        "|---|---|---|",
        f"| Accuracy (95% Wilson CI) | {lo['accuracy']} {lo['accuracy_ci95']} "
        f"| {ba['accuracy']} {ba['accuracy_ci95']} |",
        f"| Macro F1 | {lo['macro_f1']} | {ba['macro_f1']} |",
        f"| Accuracy excluding {n - hi['clauses']} clauses overlapping the training set "
        f"| {hi['lora_accuracy']} | {hi['baseline_accuracy']} |",
        "",
        f"- Evidence sufficiency vs corpus-coverage labels: **{ev['accuracy']}** "
        f"{ev['accuracy_ci95']} on {ev['conclusive']} clauses "
        f"({ev['covered_clauses']} labelled covered).",
        f"- Segmentation: exact section match on {summary['segmentation']['contracts_exact']} "
        f"of {summary['segmentation']['of']} contracts.",
        f"- Training overlap: {ov['clauses_over_threshold']} clauses exceed {ov['threshold']} "
        f"similarity to a training clause (max {ov['max_similarity']}, mean of max "
        f"{ov['mean_max_similarity']}).",
        "- Reasoning and citation verification: NOT_MEASURED (no Anthropic key).",
        "",
        "## Reading",
        "",
        "The LoRA classifier does not beat the TF-IDF baseline here; the earlier 0.59 vs 0.547 "
        "macro-F1 gap on 20 examples does not hold on 63 clauses, and the intervals overlap "
        "heavily. Segmentation fails on `kaufvertrag_maschine`: a wrapped line beginning "
        "'50 Prozent ...' is read as a numbered heading and splits clause § 2.",
        "",
        "## Limitations",
        "",
        *[f"- {x}" for x in out["limitations"]],
        "",
    ]
    (REPORT_DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
