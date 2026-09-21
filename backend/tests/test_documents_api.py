import io
from pathlib import Path

import pdfplumber
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


def test_get_report_before_analysis_is_404(client: TestClient):
    body = _upload(client, BENCHMARK_PDF, "application/pdf")
    response = client.get(f"/documents/{body['document_id']}/report")
    assert response.status_code == 404


def test_delete_document_removes_it_and_the_uploaded_file(client: TestClient):
    # Spec section 29 (Privacy): "provide cleanup/delete functionality."
    body = _upload(client, BENCHMARK_PDF, "application/pdf")
    document_id = body["document_id"]

    from app.services.pipeline.store import get_document

    stored_path = get_document(document_id).stored_path  # type: ignore[union-attr]
    assert stored_path.exists()

    delete_response = client.delete(f"/documents/{document_id}")
    assert delete_response.status_code == 204

    assert not stored_path.exists(), "uploaded file must actually be removed from disk"
    assert client.get(f"/documents/{document_id}").status_code == 404


def test_delete_unknown_document_is_404(client: TestClient):
    response = client.delete("/documents/does-not-exist")
    assert response.status_code == 404


def test_analyze_endpoint_returns_429_after_rate_limit_exceeded(
    client: TestClient, tmp_path: Path, monkeypatch
):
    # Milestone 16 Phase 17: lowers the limit (rather than making 11 real
    # analyze calls, each running the full pipeline) to keep this test fast
    # while still exercising the real HTTP path, not just the unit-level
    # rate_limit module directly.
    import app.core.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "MAX_REQUESTS_PER_WINDOW", 1)

    corrupted = tmp_path / "corrupted.pdf"
    corrupted.write_bytes(b"garbage")
    body = _upload(client, corrupted, "application/pdf")

    first = client.post(f"/documents/{body['document_id']}/analyze")
    assert first.status_code == 422  # the real corrupted-file path, still counted

    second = client.post(f"/documents/{body['document_id']}/analyze")
    assert second.status_code == 429
    assert "Rate limit exceeded" in second.json()["detail"]


def test_analyze_corrupted_upload_returns_clean_422_not_500(client: TestClient, tmp_path: Path):
    # Milestone 14: passes the extension/size checks (valid .pdf name,
    # small size) but the content is garbage - a realistic case (wrong file
    # renamed, truncated upload), not a contrived attack. Must surface as a
    # clean 422, not a raw library exception hitting the generic 500
    # handler (main.py's unhandled_error_handler, added in Milestone 12).
    corrupted = tmp_path / "corrupted.pdf"
    corrupted.write_bytes(b"not a real pdf file, just garbage bytes")
    body = _upload(client, corrupted, "application/pdf")

    response = client.post(f"/documents/{body['document_id']}/analyze")
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "PDF" in detail
    assert str(corrupted) not in detail


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

    report_response = client.get(f"/documents/{document_id}/report")
    assert report_response.status_code == 200
    assert report_response.headers["content-type"] == "application/pdf"
    assert "sample_contract_de" in report_response.headers["content-disposition"]
    assert report_response.content.startswith(b"%PDF")

    with pdfplumber.open(io.BytesIO(report_response.content)) as pdf:
        report_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    # Real clause content from the actual analyzed document, not a stub.
    # The classification asserted here is whatever the real (imperfect,
    # ~60-80% accurate - see Milestone 3/4/10) classifier actually returned
    # for this run, not a hardcoded assumption about what it "should" say.
    assert "sample_contract_de.pdf" in report_text
    assert "§ 4" in report_text
    clause_4 = next(c for c in result["clauses"] if c["clause"]["section"] == "§ 4")
    assert clause_4["classification"]["clause_type"] in report_text
