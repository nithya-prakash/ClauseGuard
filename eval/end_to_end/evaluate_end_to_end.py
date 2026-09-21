"""End-to-end pipeline evaluation (spec section 17): runs the REAL pipeline
(analyze_document) on the benchmark contract and measures each component
independently against real ground truth - nothing here is hand-typed.

Requires Qdrant running and the corpus indexed
(legal_corpus/ingestion/index_corpus.py).

This also formalizes the Milestone 10 finding into a real measured metric:
evidence-sufficiency accuracy against data/benchmark/end_to_end/ground_truth.json's
corpus_covered field (human judgment, cross-checked against the actual 15
corpus passages - see that file's _provenance).

Reasoning and citation-verification quality are NOT MEASURED here: no
ANTHROPIC_API_KEY is configured in this environment, so the LLM is never
actually called (spec section 34: report NOT MEASURED, never a fabricated
number). See reports/reasoning/report.md for that explicit placeholder.

Usage:
    QDRANT_URL=http://localhost:6339 python eval/end_to_end/evaluate_end_to_end.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.pipeline.document_analysis import analyze_document  # noqa: E402

GROUND_TRUTH_PATH = ROOT / "data" / "benchmark" / "end_to_end" / "ground_truth.json"
REPORT_DIR = ROOT / "reports" / "end_to_end"
REASONING_REPORT_DIR = ROOT / "reports" / "reasoning"


def _actual_sufficiency(reasoning_status: str | None, reasoning_error: str | None) -> bool | None:
    """True = evidence was judged sufficient, False = insufficient, None =
    inconclusive (an unexpected pipeline failure, not a clean signal)."""
    if reasoning_status == "INSUFFICIENT_EVIDENCE":
        return False
    if reasoning_error and "ANTHROPIC_API_KEY" in reasoning_error:
        # LLMNotConfiguredError is only raised AFTER evidence was judged
        # sufficient (see reasoning/service.py) - so this is a clean signal.
        return True
    return None


def main() -> None:
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)

    result = analyze_document(Path(ROOT / ground_truth["contract"]), client)

    gt_by_position = {c["position"]: c for c in ground_truth["clauses"]}

    segmentation_pass = result.clause_count == len(ground_truth["clauses"])

    classification_correct = 0
    classification_failures = 0
    sufficiency_correct = 0
    sufficiency_inconclusive = 0
    sufficiency_total_conclusive = 0
    reasoning_attempts = 0  # clauses where the LLM would have been called
    per_clause_rows = []

    for ca in result.clauses:
        gt = gt_by_position[ca.clause.position]

        classification_ok = (
            ca.classification is not None
            and ca.classification.clause_type == gt["expected_clause_type"]
        )
        if ca.classification is None:
            classification_failures += 1
        elif classification_ok:
            classification_correct += 1

        reasoning_status = ca.reasoning.status if ca.reasoning else None
        actual_sufficient = _actual_sufficiency(reasoning_status, ca.reasoning_error)
        if actual_sufficient is None:
            sufficiency_inconclusive += 1
        else:
            sufficiency_total_conclusive += 1
            if actual_sufficient == gt["corpus_covered"]:
                sufficiency_correct += 1
            if actual_sufficient:
                reasoning_attempts += 1

        per_clause_rows.append(
            {
                "position": ca.clause.position,
                "section": ca.clause.section,
                "expected_clause_type": gt["expected_clause_type"],
                "predicted_clause_type": (
                    ca.classification.clause_type if ca.classification else None
                ),
                "classification_correct": classification_ok,
                "expected_corpus_covered": gt["corpus_covered"],
                "actual_sufficient": actual_sufficient,
                "reasoning_status": reasoning_status,
                "reasoning_error": ca.reasoning_error,
            }
        )

    n = len(ground_truth["clauses"])
    output = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "contract": ground_truth["contract"],
        "clause_count": n,
        "components": {
            "segmentation": {
                "expected_clause_count": n,
                "actual_clause_count": result.clause_count,
                "pass": segmentation_pass,
            },
            "classification": {
                "accuracy": round(classification_correct / n, 4),
                "failures": classification_failures,
                "model": "lora-distilbert-multilingual-v1 (falls back to baseline if untrained)",
            },
            "evidence_sufficiency": {
                "accuracy": (
                    round(sufficiency_correct / sufficiency_total_conclusive, 4)
                    if sufficiency_total_conclusive
                    else None
                ),
                "conclusive_clauses": sufficiency_total_conclusive,
                "inconclusive_clauses": sufficiency_inconclusive,
                "note": (
                    "Measures whether the sufficiency gate's SUFFICIENT/INSUFFICIENT "
                    "decision matches human judgment of real corpus coverage "
                    "(data/benchmark/end_to_end/ground_truth.json). This is the "
                    "Milestone 10 finding, now a real measured number."
                ),
            },
            "reasoning": {
                "status": "NOT_MEASURED",
                "reason": "No ANTHROPIC_API_KEY configured in this environment - the "
                "LLM was never called. See reports/reasoning/report.md.",
                "clauses_that_would_have_reached_llm": reasoning_attempts,
            },
            "citation_verification": {
                "status": "NOT_MEASURED",
                "reason": "Depends on real LLM output (see 'reasoning' above). The "
                "citation verification logic itself is unit-tested against "
                "constructed adversarial findings - see "
                "backend/tests/test_citation_verification.py.",
            },
            "report_generation": {
                "status": "NOT_APPLICABLE",
                "reason": "Not yet implemented (Milestone 13).",
            },
        },
        "pipeline_failures": {
            "classification_failures": classification_failures,
            "sufficiency_inconclusive": sufficiency_inconclusive,
        },
        "per_clause": per_clause_rows,
        "limitations": [
            "Single benchmark contract (10 clauses) - measures whether the wired "
            "pipeline behaves correctly, not statistically robust component accuracy.",
            "Reasoning/citation-verification quality genuinely not measured (no LLM "
            "call made), not omitted for convenience.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# End-to-end pipeline evaluation report",
        "",
        f"Generated: {output['evaluated_at']}",
        f"Contract: {output['contract']} ({n} clauses)",
        "",
        "## Component results",
        "",
        f"- Segmentation: {result.clause_count}/{n} clauses detected "
        f"({'PASS' if segmentation_pass else 'FAIL'})",
        f"- Classification accuracy: **{output['components']['classification']['accuracy']}** "
        f"({classification_failures} failures)",
        f"- Evidence sufficiency accuracy: "
        f"**{output['components']['evidence_sufficiency']['accuracy']}** "
        f"({sufficiency_total_conclusive} conclusive / {sufficiency_inconclusive} inconclusive)",
        f"- Reasoning: **NOT_MEASURED** (no ANTHROPIC_API_KEY; "
        f"{reasoning_attempts} clauses would have reached the LLM)",
        "- Citation verification: **NOT_MEASURED** (depends on reasoning)",
        "- Report generation: **NOT_APPLICABLE** (Milestone 13 not yet built)",
        "",
        "## Per-clause detail",
        "",
        "| § | Expected type | Predicted type | Class. OK | Corpus covered | Sufficient? |",
        "|---|---|---|---|---|---|",
    ]
    for row in per_clause_rows:
        lines.append(
            f"| {row['section']} | {row['expected_clause_type']} | "
            f"{row['predicted_clause_type']} | {row['classification_correct']} | "
            f"{row['expected_corpus_covered']} | {row['actual_sufficient']} |"
        )
    lines += ["", "## Limitations", ""]
    lines += [f"- {limitation}" for limitation in output["limitations"]]
    (REPORT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    _write_reasoning_not_measured_stub()

    print(json.dumps(output, indent=2, ensure_ascii=False))


def _write_reasoning_not_measured_stub() -> None:
    REASONING_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stub = {
        "status": "NOT_MEASURED",
        "reason": "No ANTHROPIC_API_KEY configured in this environment - the LLM "
        "reasoning stage (Milestone 9) has never actually been called, so there is "
        "no real accuracy/hallucination-rate/citation-correctness number to report. "
        "Per the project's anti-fabrication policy, no placeholder number is given.",
        "what_is_built_and_tested": [
            "Structured output schema + tool-use call (backend/app/services/reasoning/client.py)",
            "Prompt-injection defenses (backend/app/services/reasoning/prompts.py)",
            "Evidence-sufficiency gating and citation verification wiring "
            "(backend/app/services/reasoning/service.py)",
            "A live-call test exists and is ready, gated on ANTHROPIC_API_KEY "
            "(backend/tests/test_reasoning_client.py::test_live_llm_call_returns_schema_valid_output)",
        ],
        "how_to_measure": "Set ANTHROPIC_API_KEY, then run "
        "eval/end_to_end/evaluate_end_to_end.py again - reasoning_attempts clauses "
        "will produce real ReasoningResult objects instead of LLMNotConfiguredError.",
    }
    (REASONING_REPORT_DIR / "results.json").write_text(
        json.dumps(stub, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (REASONING_REPORT_DIR / "report.md").write_text(
        "# Reasoning evaluation report\n\n"
        "**Status: NOT_MEASURED**\n\n"
        f"{stub['reason']}\n\n"
        "## What is built and tested\n\n"
        + "\n".join(f"- {item}" for item in stub["what_is_built_and_tested"])
        + f"\n\n## How to measure\n\n{stub['how_to_measure']}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
