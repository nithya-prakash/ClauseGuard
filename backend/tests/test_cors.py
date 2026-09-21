"""Regression test for a real bug found in Milestone 12: the frontend
(served from localhost:3005/3006) couldn't call the API at all because CORS
only allowed a hardcoded localhost:3000 that nothing actually uses."""

from fastapi.testclient import TestClient


def test_cors_allows_configured_frontend_origins(client: TestClient):
    for origin in ("http://localhost:3005", "http://localhost:3006"):
        response = client.get("/health", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unlisted_origin(client: TestClient):
    response = client.get("/health", headers={"Origin": "http://evil.example.com"})
    assert response.headers.get("access-control-allow-origin") is None
