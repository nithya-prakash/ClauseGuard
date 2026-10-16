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


def test_call_ollama_posts_schema_constrained_request_and_parses_json(monkeypatch):
    import json

    from app.services.reasoning import client

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": json.dumps({"clause_id": "c1"})}}

    def fake_post(url, json=None, timeout=None):
        captured.update(url=url, body=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(client.httpx, "post", fake_post)
    out = client.call_ollama("http://ollama:11434/", "qwen2.5:7b", "c1", "text", "Haftung", [])

    assert out == {"clause_id": "c1"}
    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["body"]["format"] == TOOL_SCHEMA["input_schema"]
    assert captured["body"]["stream"] is False


def test_call_ollama_wraps_connection_errors(monkeypatch):
    import httpx

    from app.core.exceptions import PipelineStageError
    from app.services.reasoning import client

    def fail(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(client.httpx, "post", fail)
    with pytest.raises(PipelineStageError):
        client.call_ollama("http://ollama:11434", "m", "c1", "t", "Haftung", [])
