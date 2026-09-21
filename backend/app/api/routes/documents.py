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
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.core.exceptions import (
    FileTooLargeError,
    NotFoundError,
    ReportNotImplementedError,
    UnsupportedFileTypeError,
)
from app.schemas.clause import Clause
from app.schemas.pipeline import DocumentAnalysisResult
from app.services.pipeline.document_analysis import analyze_document
from app.services.pipeline.store import (
    DocumentRecord,
    get_document,
    get_result,
    save_document,
    save_result,
)

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


@router.get("/{document_id}/report")
def get_report(document_id: str) -> None:
    _get_document_or_404(document_id)
    raise ReportNotImplementedError(
        "PDF report generation is not yet implemented (Milestone 13)."
    )
