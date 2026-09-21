"""Async analysis job persistence (Milestone 16 Phase 15) - backs the
additive API -> Job creation -> Celery/worker -> pipeline -> Postgres path
(backend/app/api/routes/jobs.py, backend/app/tasks/analysis.py), alongside
the existing synchronous POST /documents/{id}/analyze endpoint. See
store.py's module docstring for why `_db.SessionLocal` is read at call time
rather than imported directly - the same reasoning applies here."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core import db as _db
from app.models.document import AnalysisJobModel

JobStatus = str  # "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"


@dataclass
class AnalysisJob:
    job_id: str
    document_id: str
    status: JobStatus
    error: str | None
    created_at: datetime
    completed_at: datetime | None


def _to_dataclass(row: AnalysisJobModel) -> AnalysisJob:
    return AnalysisJob(
        job_id=row.job_id,
        document_id=row.document_id,
        status=row.status,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


def create_job(document_id: str) -> AnalysisJob:
    job_id = uuid.uuid4().hex
    with _db.SessionLocal() as session:
        row = AnalysisJobModel(
            job_id=job_id,
            document_id=document_id,
            status="PENDING",
            created_at=datetime.now(UTC),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_dataclass(row)


def get_job(job_id: str) -> AnalysisJob | None:
    with _db.SessionLocal() as session:
        row = session.get(AnalysisJobModel, job_id)
        return _to_dataclass(row) if row is not None else None


def update_job_status(job_id: str, status: JobStatus, error: str | None = None) -> None:
    with _db.SessionLocal() as session:
        row = session.get(AnalysisJobModel, job_id)
        if row is None:
            return
        row.status = status
        row.error = error
        if status in ("COMPLETED", "FAILED"):
            row.completed_at = datetime.now(UTC)
        session.commit()
