from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PDF = REPO_ROOT / "data" / "benchmark" / "segmentation" / "sample_contract_de.pdf"


def _upload(client: TestClient, path: Path, content_type: str) -> dict:
    with path.open("rb") as f:
        response = client.post(
            "/documents", files={"file": (path.name, f, content_type)}
        )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def test_upload_pdf_returns_document_id(client: TestClient):
    body = _upload(client, BENCHMARK_PDF, "application/pdf")
    assert "document_id" in body
    assert body["filename"] == "sample_contract_de.pdf"
    assert body["size_bytes"] > 0


def test_upload_rejects_unsupported_file_type(client: TestClient, tmp_path: Path):
    bogus = tmp_path / "not_a_contract.txt"
    bogus.write_text("irrelevant")
    with bogus.open("rb") as f:
        response = client.post(
            "/documents", files={"file": ("not_a_contract.txt", f, "text/plain")}
        )
    assert response.status_code == 415


def test_upload_rejects_oversized_file(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "0")
    get_settings.cache_clear()
    try:
        with BENCHMARK_PDF.open("rb") as f:
            response = client.post(
                "/documents", files={"file": ("sample_contract_de.pdf", f, "application/pdf")}
            )
        assert response.status_code == 413
    finally:
        monkeypatch.delenv("MAX_UPLOAD_SIZE_MB", raising=False)
        get_settings.cache_clear()


def test_get_document_metadata_for_unknown_id_is_404(client: TestClient):
    response = client.get("/documents/does-not-exist")
    assert response.status_code == 404


def test_get_clauses_before_analysis_is_404(client: TestClient):
    body = _upload(client, BENCHMARK_PDF, "application/pdf")
    response = client.get(f"/documents/{body['document_id']}/clauses")
    assert response.status_code == 404


def test_get_report_is_not_implemented(client: TestClient):
    body = _upload(client, BENCHMARK_PDF, "application/pdf")
    response = client.get(f"/documents/{body['document_id']}/report")
    assert response.status_code == 501
    assert "Milestone 13" in response.json()["detail"]


@pytest.mark.integration
def test_upload_then_analyze_then_fetch_findings(client: TestClient):
    body = _upload(client, BENCHMARK_PDF, "application/pdf")
    document_id = body["document_id"]

    analyze_response = client.post(f"/documents/{document_id}/analyze")
    assert analyze_response.status_code == 200, analyze_response.text
    result = analyze_response.json()
    assert result["clause_count"] == 10
    assert len(result["clauses"]) == 10
    # Must show the user's original filename, not the server-generated
    # UUID-based stored filename (a real bug found and fixed in Milestone 12).
    assert result["filename"] == "sample_contract_de.pdf"

    findings_response = client.get(f"/documents/{document_id}/findings")
    assert findings_response.status_code == 200
    assert findings_response.json()["clause_count"] == 10

    clauses_response = client.get(f"/documents/{document_id}/clauses")
    assert clauses_response.status_code == 200
    assert len(clauses_response.json()) == 10

    metadata_response = client.get(f"/documents/{document_id}")
    assert metadata_response.json()["analyzed"] is True
