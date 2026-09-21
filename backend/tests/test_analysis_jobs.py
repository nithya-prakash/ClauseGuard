"""Milestone 16 Phase 15: the async job path (API -> Job creation -> Celery
-> pipeline -> Postgres -> Qdrant), additive alongside the existing
synchronous /analyze endpoint. Needs real Postgres + Qdrant (and, for the
task-logic test, no broker - Celery's `.apply()` runs a task synchronously
in-process; the HTTP-path test uses `task_always_eager` for the same
reason, a standard Celery testing pattern that avoids needing an actual
running worker process during pytest)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.celery_app import celery_app
from app.services.pipeline.jobs_store import create_job, get_job
from app.services.pipeline.store import DocumentRecord, get_result, save_document
from app.tasks.analysis import run_document_analysis

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PDF = REPO_ROOT / "data" / "benchmark" / "segmentation" / "sample_contract_de.pdf"


@pytest.mark.integration
def test_run_document_analysis_task_persists_result_and_completes_job():
    """Calls the real task function synchronously (no broker) against real
    Postgres + Qdrant, and checks it actually wrote a real, retrievable
    result - not just that it returned without raising."""
    document_id = "task-test-doc"
    save_document(
        DocumentRecord(
            document_id=document_id,
            original_filename="sample_contract_de.pdf",
            stored_path=BENCHMARK_PDF,
            content_type="application/pdf",
        )
    )
    job = create_job(document_id)

    run_document_analysis.apply(args=(job.job_id, document_id))

    completed_job = get_job(job.job_id)
    assert completed_job is not None
    assert completed_job.status == "COMPLETED"
    assert completed_job.error is None
    assert completed_job.completed_at is not None

    result = get_result(document_id)
    assert result is not None
    assert result.clause_count == 10


@pytest.mark.integration
def test_run_document_analysis_task_marks_job_failed_on_bad_document_id():
    job = create_job("does-not-exist")
    run_document_analysis.apply(args=(job.job_id, "does-not-exist"))

    failed_job = get_job(job.job_id)
    assert failed_job is not None
    assert failed_job.status == "FAILED"
    assert failed_job.error is not None


@pytest.mark.integration
def test_async_job_http_path_end_to_end(client: TestClient):
    """The full HTTP contract: POST creates a job, GET polls it to
    completion, and the result matches what the synchronous /analyze
    endpoint would have returned. task_always_eager makes .delay() run
    in-process (no live worker process needed for this test) - the task
    function itself is identical to what the real worker container runs."""
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        with BENCHMARK_PDF.open("rb") as f:
            upload = client.post(
                "/documents", files={"file": ("sample_contract_de.pdf", f, "application/pdf")}
            )
        document_id = upload.json()["document_id"]

        create_response = client.post(f"/documents/{document_id}/jobs")
        assert create_response.status_code == 202, create_response.text
        job_id = create_response.json()["job_id"]

        status_response = client.get(f"/documents/{document_id}/jobs/{job_id}")
        assert status_response.status_code == 200
        body = status_response.json()
        assert body["status"] == "COMPLETED"
        assert body["result"]["clause_count"] == 10
        assert body["result"]["filename"] == "sample_contract_de.pdf"
    finally:
        celery_app.conf.task_always_eager = original_eager


@pytest.mark.integration
def test_get_job_for_unknown_job_id_is_404(client: TestClient):
    with BENCHMARK_PDF.open("rb") as f:
        upload = client.post(
            "/documents", files={"file": ("sample_contract_de.pdf", f, "application/pdf")}
        )
    document_id = upload.json()["document_id"]
    response = client.get(f"/documents/{document_id}/jobs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.integration
def test_create_job_for_unknown_document_is_404(client: TestClient):
    response = client.post("/documents/does-not-exist/jobs")
    assert response.status_code == 404
