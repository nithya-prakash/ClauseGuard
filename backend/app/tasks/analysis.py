"""Milestone 16 Phase 15: the real Celery-executed half of the async
analysis path (API -> Job creation -> Celery/worker -> analysis pipeline ->
Postgres persistence -> Qdrant retrieval). Registered on celery_app via
core/celery_app.py's `include`, and run by the `worker` docker-compose
service (which already has its own healthcheck from Milestone 12 - this is
the first real task it has ever had to execute).

A task-level failure (corrupted upload, no trained classifier, etc.) is
caught and recorded on the job row as FAILED with the real error message,
never left PENDING/RUNNING forever and never silently swallowed.
"""

from qdrant_client import QdrantClient

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.exceptions import ClauseGuardError
from app.core.logging import get_logger
from app.services.pipeline.document_analysis import analyze_document
from app.services.pipeline.jobs_store import update_job_status
from app.services.pipeline.store import get_document, save_result

logger = get_logger(__name__)


@celery_app.task(name="clauseguard.run_document_analysis")
def run_document_analysis(job_id: str, document_id: str) -> None:
    update_job_status(job_id, "RUNNING")
    try:
        record = get_document(document_id)
        if record is None:
            raise ValueError(f"No document with id '{document_id}'.")

        settings = get_settings()
        client = QdrantClient(url=settings.qdrant_url)
        result = analyze_document(record.stored_path, client)
        result.filename = record.original_filename
        save_result(document_id, result)

        update_job_status(job_id, "COMPLETED")
    except ClauseGuardError as exc:
        logger.warning(
            "analysis_job_failed", job_id=job_id, document_id=document_id, error=str(exc)
        )
        update_job_status(job_id, "FAILED", error=str(exc))
    except Exception as exc:  # noqa: BLE001 - a job must always end in a terminal
        # status, never left RUNNING forever because of an unexpected
        # exception type; the real exception is logged, not leaked to the
        # job row's error field (which is API-visible).
        logger.error(
            "analysis_job_unexpected_failure",
            job_id=job_id,
            document_id=document_id,
            error=str(exc),
        )
        update_job_status(job_id, "FAILED", error="Analysis failed due to an internal error.")
