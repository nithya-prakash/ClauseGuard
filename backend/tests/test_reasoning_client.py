import os

import pytest

from app.schemas.reasoning import RawReasoningOutput
from app.schemas.retrieval import RetrievedPassage
from app.services.classification.labels import CLAUSE_LABELS
from app.services.reasoning.client import TOOL_SCHEMA, call_llm

HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


def test_tool_schema_risk_level_enum_matches_documented_categories():
    props = TOOL_SCHEMA["input_schema"]["properties"]
    assert props["risk_level"]["enum"] == ["LOW", "MEDIUM", "HIGH"]
    assert "INSUFFICIENT_EVIDENCE" not in props["risk_level"]["enum"], (
        "INSUFFICIENT_EVIDENCE is a system-only status set before the LLM is "
        "called (see evidence_sufficiency.py) - the model must not be able "
        "to emit it itself."
    )


def test_tool_schema_classification_enum_matches_clause_labels():
    props = TOOL_SCHEMA["input_schema"]["properties"]
    assert props["classification"]["enum"] == CLAUSE_LABELS


def test_tool_schema_requires_all_top_level_fields():
    schema = TOOL_SCHEMA["input_schema"]
    assert set(schema["required"]) == {
        "clause_id",
        "classification",
        "risk_level",
        "status",
        "findings",
        "explanation",
        "confidence",
        "limitations",
    }


@pytest.mark.integration
@pytest.mark.skipif(not HAS_API_KEY, reason="ANTHROPIC_API_KEY not set - live LLM test skipped")
def test_live_llm_call_returns_schema_valid_output():
    """Ready to run once a real key is configured; not run otherwise (never
    faked - see LLMNotConfiguredError gating in reasoning/service.py)."""
    evidence = [
        RetrievedPassage(
            source="BGB",
            section="§ 276",
            title="Verantwortlichkeit des Schuldners",
            text="(1) Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten.",
            source_url="https://www.gesetze-im-internet.de/bgb/__276.html",
            score=0.9,
            method="hybrid_rrf_reranked",
        )
    ]
    raw = call_llm(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model="claude-sonnet-5",
        clause_id="c1",
        clause_text="Der Verkäufer haftet nur für Vorsatz und grobe Fahrlässigkeit.",
        classification="LIABILITY",
        evidence=evidence,
    )
    validated = RawReasoningOutput.model_validate(raw)
    assert validated.clause_id == "c1"
    assert validated.risk_level in ("LOW", "MEDIUM", "HIGH")
