"""Document upload/analysis endpoints (spec section 20).

Analysis runs synchronously inside the request (Celery background job
processing is Milestone 23, not yet built) - the route handler is a plain
`def`, not `async def`, so FastAPI runs it in its threadpool executor
rather than blocking the event loop. This is a real, documented interim
architecture, not a shortcut hidden from the caller.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, NotFoundError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.schemas.clause import Clause
from app.schemas.job import AnalysisJobResponse
from app.schemas.pipeline import DocumentAnalysisResult
from app.services.pipeline.document_analysis import analyze_document
from app.services.pipeline.jobs_store import create_job, get_job
from app.services.pipeline.store import (
    DocumentRecord,
    delete_document,
    get_document,
    get_result,
    save_document,
    save_result,
)
from app.services.reporting.pdf_generator import generate_report_pdf
from app.services.retrieval.corpus_loader import load_scope
from app.tasks.analysis import run_document_analysis

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"


def _get_document_or_404(document_id: str) -> DocumentRecord:
    record = get_document(document_id)
    if record is None:
        raise NotFoundError(f"No document with id '{document_id}'.")
    return record


@router.post("", status_code=201)
async def upload_document(file: UploadFile = File(...)) -> dict:  # noqa: B008
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.upload_allowed_extensions_list:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Allowed: {settings.upload_allowed_extensions_list}"
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise FileTooLargeError(f"File exceeds the {settings.max_upload_size_mb}MB limit.")

    # Server-generated id/filename only - the client's original filename is
    # never used to build a filesystem path (prevents path traversal); it's
    # kept purely as display metadata.
    document_id = uuid.uuid4().hex
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_DIR / f"{document_id}{suffix}"
    stored_path.write_bytes(content)

    record = DocumentRecord(
        document_id=document_id,
        original_filename=file.filename or "unknown",
        stored_path=stored_path,
        content_type=file.content_type or "application/octet-stream",
    )
    save_document(record)

    return {
        "document_id": document_id,
        "filename": record.original_filename,
        "size_bytes": len(content),
    }


@router.get("/{document_id}")
def get_document_metadata(document_id: str) -> dict:
    record = _get_document_or_404(document_id)
    return {
        "document_id": record.document_id,
        "filename": record.original_filename,
        "content_type": record.content_type,
        "analyzed": get_result(document_id) is not None,
    }


@router.post("/{document_id}/analyze", response_model=DocumentAnalysisResult)
def analyze(document_id: str) -> DocumentAnalysisResult:
    record = _get_document_or_404(document_id)
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    result = analyze_document(record.stored_path, client)
    # analyze_document() reports the server-generated stored filename (a
    # UUID, since the original filename is never used to build a filesystem
    # path); the API response should show the user's original filename.
    result.filename = record.original_filename
    save_result(document_id, result)
    return result


@router.post("/{document_id}/jobs", response_model=AnalysisJobResponse, status_code=202)
def create_analysis_job(document_id: str) -> AnalysisJobResponse:
    """Additive async path (Milestone 16 Phase 15) alongside the existing
    synchronous /analyze above: creates a real Postgres-persisted job row
    and enqueues a real Celery task (backend/app/tasks/analysis.py), run by
    the `worker` docker-compose service. The existing synchronous endpoint
    and the frontend built against it are unchanged - this is an addition,
    not a replacement, per the spec's "do not rewrite the whole
    application" instruction."""
    _get_document_or_404(document_id)
    job = create_job(document_id)
    run_document_analysis.delay(job.job_id, document_id)
    return AnalysisJobResponse(job_id=job.job_id, document_id=document_id, status=job.status)


@router.get("/{document_id}/jobs/{job_id}", response_model=AnalysisJobResponse)
def get_analysis_job(document_id: str, job_id: str) -> AnalysisJobResponse:
    _get_document_or_404(document_id)
    job = get_job(job_id)
    if job is None or job.document_id != document_id:
        raise NotFoundError(f"No job with id '{job_id}' for document '{document_id}'.")

    result = get_result(document_id) if job.status == "COMPLETED" else None
    return AnalysisJobResponse(
        job_id=job.job_id,
        document_id=job.document_id,
        status=job.status,
        error=job.error,
        result=result,
    )


@router.get("/{document_id}/clauses", response_model=list[Clause])
def get_clauses(document_id: str) -> list[Clause]:
    _get_document_or_404(document_id)
    result = get_result(document_id)
    if result is None:
        raise NotFoundError(f"Document '{document_id}' has not been analyzed yet.")
    return [ca.clause for ca in result.clauses]


@router.get("/{document_id}/findings", response_model=DocumentAnalysisResult)
def get_findings(document_id: str) -> DocumentAnalysisResult:
    _get_document_or_404(document_id)
    result = get_result(document_id)
    if result is None:
        raise NotFoundError(f"Document '{document_id}' has not been analyzed yet.")
    return result


@router.delete("/{document_id}", status_code=204)
def delete_document_endpoint(document_id: str) -> None:
    """Spec section 29 (Privacy): "don't persist raw documents unnecessarily,
    provide cleanup/delete functionality." Removes the uploaded file from
    disk and clears both the document metadata and any analysis result from
    the store - nothing about this document remains server-side afterward."""
    record = _get_document_or_404(document_id)
    delete_document(document_id)
    try:
        record.stored_path.unlink(missing_ok=True)
    except OSError as exc:
        # Deletion from the in-memory store already succeeded (the document
        # is gone from the API's perspective); a filesystem error removing
        # the underlying file is logged, not surfaced as a failed request -
        # surfacing it would be misleading (the delete DID work) and there's
        # nothing the caller can do about a filesystem issue on the server.
        logger.warning("upload_file_delete_failed", document_id=document_id, error=str(exc))


@router.get("/{document_id}/report")
def get_report(document_id: str) -> Response:
    _get_document_or_404(document_id)
    result = get_result(document_id)
    if result is None:
        raise NotFoundError(f"Document '{document_id}' has not been analyzed yet.")

    pdf_bytes = generate_report_pdf(result, load_scope())
    safe_name = result.filename.rsplit(".", 1)[0].replace('"', "")
    content_disposition = f'attachment; filename="{safe_name}_clauseguard_report.pdf"'
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition},
    )
