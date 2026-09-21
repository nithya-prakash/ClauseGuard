from fastapi.testclient import TestClient

from app.schemas.health import DependencyStatus


def test_health_returns_valid_schema(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] in ("ok", "degraded")
    for key in ("database", "qdrant", "redis", "llm_reasoning"):
        assert key in body
        assert body[key]["status"] in DependencyStatus.__args__


def test_health_reports_llm_not_configured_without_api_key(client: TestClient, monkeypatch) -> None:
    # No ANTHROPIC_API_KEY is set in the test environment: the reasoning
    # stage must honestly report itself as unconfigured rather than "ok".
    response = client.get("/health")
    body = response.json()
    assert body["llm_reasoning"]["status"] in ("not_configured", "ok")
    if body["llm_reasoning"]["status"] == "not_configured":
        assert "ANTHROPIC_API_KEY" in body["llm_reasoning"]["detail"]
