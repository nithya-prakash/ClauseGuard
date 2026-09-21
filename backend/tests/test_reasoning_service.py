import pytest
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.core.exceptions import LLMNotConfiguredError
from app.services.reasoning.service import assess_clause


@pytest.mark.integration
def test_off_topic_clause_short_circuits_to_insufficient_evidence_without_llm():
    """No ANTHROPIC_API_KEY is set in this environment - if assess_clause
    tried to call the LLM for this clause, it would raise
    LLMNotConfiguredError. It must not: an off-topic clause is decided
    INSUFFICIENT_EVIDENCE before that branch is ever reached."""
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)

    result = assess_clause(
        client,
        clause_id="c1",
        clause_text="Wie repariere ich die Kette an meinem Fahrrad?",
        classification="OTHER",
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.risk_level == "INSUFFICIENT_EVIDENCE"
    assert result.findings == []


@pytest.mark.integration
def test_relevant_clause_without_api_key_raises_llm_not_configured():
    settings = get_settings()
    assert not settings.llm_configured, (
        "This test asserts the honest-gating behavior for the no-key case; "
        "it is not meaningful once a real ANTHROPIC_API_KEY is configured."
    )
    client = QdrantClient(url=settings.qdrant_url)

    with pytest.raises(LLMNotConfiguredError):
        assess_clause(
            client,
            clause_id="c1",
            clause_text="Der Verkäufer haftet nur für Vorsatz und grobe Fahrlässigkeit.",
            classification="LIABILITY",
        )
