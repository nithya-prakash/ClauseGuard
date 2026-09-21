"""Milestone 16 Phase 12-13: real Claude reasoning evaluation, gated on
ANTHROPIC_API_KEY. Requires Qdrant running and the corpus indexed
(legal_corpus/ingestion/index_corpus.py).

This script does NOT fabricate a result when no key is configured - it
writes an explicit NOT_MEASURED report and exits cleanly, exactly like
eval/end_to_end/evaluate_end_to_end.py's reasoning stub. When a key IS
configured, it calls the real LLM for every example in
data/benchmark/reasoning/dataset.json and measures:
  - schema validity (did assess_clause() return without raising
    PipelineStageError - i.e. the LLM's raw output validated against
    RawReasoningOutput)
  - citation correctness (the real citation_status from
    verification/citation.py - VERIFIED vs CITATION_UNVERIFIED - not a
    re-implemented check)
  - primary-citation match rate (does at least one finding cite the
    section a human already confirmed is the real relevant evidence -
    a grounding check, not a legal-accuracy claim)
  - unsupported-claim rate (findings whose citation_status is
    CITATION_UNVERIFIED - the model claimed a citation that does not hold
    up against what was actually retrieved)

Deliberately NOT measured (no ground truth exists for these - see
dataset.json's annotation_criteria): whether the model's risk_level
(LOW/MEDIUM/HIGH) is legally correct.

Usage:
    ANTHROPIC_API_KEY=... QDRANT_URL=http://localhost:6339 \
        python eval/reasoning/evaluate_reasoning.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.reasoning.service import assess_clause  # noqa: E402

DATASET_PATH = ROOT / "data" / "benchmark" / "reasoning" / "dataset.json"
REPORT_DIR = ROOT / "reports" / "reasoning"


def _not_measured_report(reason: str) -> dict:
    return {
        "status": "NOT_MEASURED",
        "reason": reason,
        "what_is_built_and_tested": [
            "Structured output schema + tool-use call (backend/app/services/reasoning/client.py)",
            "Prompt-injection defenses (backend/app/services/reasoning/prompts.py)",
            "Evidence-sufficiency gating and citation verification wiring "
            "(backend/app/services/reasoning/service.py)",
            "A live-call test exists and is ready, gated on ANTHROPIC_API_KEY "
            "(backend/tests/test_reasoning_client.py::test_live_llm_call_returns_schema_valid_output)",
            "This dedicated 8-example reasoning evaluation harness "
            "(data/benchmark/reasoning/dataset.json, eval/reasoning/evaluate_reasoning.py) "
            "- built and ready, never run against a real key in this environment.",
        ],
        "how_to_measure": "Set ANTHROPIC_API_KEY, then re-run this script.",
    }


def main() -> None:
    settings = get_settings()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not settings.llm_configured:
        report = _not_measured_report(
            "No ANTHROPIC_API_KEY configured in this environment - the LLM reasoning "
            "stage has never actually been called for this benchmark, so there is no "
            "real schema-validity/citation-correctness/hallucination number to report. "
            "Per the project's anti-fabrication policy, no placeholder number is given."
        )
        (REPORT_DIR / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (REPORT_DIR / "report.md").write_text(
            "# Reasoning evaluation report\n\n**Status: NOT_MEASURED**\n\n"
            f"{report['reason']}\n\n## What is built and tested\n\n"
            + "\n".join(f"- {item}" for item in report["what_is_built_and_tested"])
            + f"\n\n## How to measure\n\n{report['how_to_measure']}\n",
            encoding="utf-8",
        )
        print("No ANTHROPIC_API_KEY configured - wrote NOT_MEASURED report, made no LLM calls.")
        return

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    client = QdrantClient(url=settings.qdrant_url)

    rows = []
    for clause in dataset["clauses"]:
        result = assess_clause(
            client, clause["clause_id"], clause["clause_text"], clause["clause_type"]
        )
        primary_match = any(
            clause["expected_primary_citation_section"] in f.citation for f in result.findings
        )
        rows.append(
            {
                "clause_id": clause["clause_id"],
                "expected_primary_citation_section": clause["expected_primary_citation_section"],
                "status": result.status,
                "risk_level": result.risk_level,
                "finding_count": len(result.findings),
                "citations": [f.citation for f in result.findings],
                "citation_statuses": [f.citation_status for f in result.findings],
                "primary_citation_matched": primary_match,
                "schema_valid": True,  # reaching this point means RawReasoningOutput validated
            }
        )

    n = len(rows)
    schema_valid_count = sum(1 for r in rows if r["schema_valid"])
    primary_match_count = sum(1 for r in rows if r["primary_citation_matched"])
    all_citation_statuses = [s for r in rows for s in r["citation_statuses"]]
    verified_count = sum(1 for s in all_citation_statuses if s == "VERIFIED")
    unverified_count = sum(1 for s in all_citation_statuses if s == "CITATION_UNVERIFIED")

    output = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "dataset": str(DATASET_PATH.relative_to(ROOT)),
        "clause_count": n,
        "model": settings.anthropic_model,
        "results": {
            "schema_validity_rate": round(schema_valid_count / n, 4),
            "primary_citation_match_rate": round(primary_match_count / n, 4),
            "total_findings": len(all_citation_statuses),
            "citation_verified_count": verified_count,
            "citation_unverified_count": unverified_count,
            "citation_verified_rate": (
                round(verified_count / len(all_citation_statuses), 4)
                if all_citation_statuses
                else None
            ),
        },
        "not_measured": {
            "risk_level_legal_accuracy": (
                "No ground truth exists for whether LOW/MEDIUM/HIGH is the legally "
                "correct assessment - this project does not assert legal judgments as "
                "ground truth. See README's legal disclaimer."
            )
        },
        "per_clause": rows,
    }

    (REPORT_DIR / "results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = [
        "# Reasoning evaluation report",
        "",
        f"Generated: {output['evaluated_at']}",
        f"Model: {output['model']}",
        f"Clauses: {n}",
        "",
        "## Results",
        "",
        f"- Schema validity rate: **{output['results']['schema_validity_rate']}**",
        f"- Primary-citation match rate: **{output['results']['primary_citation_match_rate']}**",
        f"- Citation verified rate: **{output['results']['citation_verified_rate']}** "
        f"({verified_count}/{len(all_citation_statuses)} findings)",
        "",
        "## NOT measured",
        "",
        f"- {output['not_measured']['risk_level_legal_accuracy']}",
        "",
        "## Per-clause detail",
        "",
        "| clause_id | expected citation | status | risk_level | primary match | citations |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['clause_id']} | {r['expected_primary_citation_section']} | {r['status']} | "
            f"{r['risk_level']} | {r['primary_citation_matched']} | {r['citations']} |"
        )
    (REPORT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
