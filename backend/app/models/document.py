"""Milestone 16 Phase 15: SQLAlchemy models backing document/analysis
persistence. Uses the generic SQLAlchemy `JSON` type (not Postgres-specific
JSONB) and timezone-AWARE datetimes throughout, specifically so these models
work identically against both the real Postgres used in Docker/production
and the in-memory SQLite used for the fast unit-test tier (see
backend/tests/conftest.py) - a JSONB or naive-datetime column would silently
break under SQLite, a known trap (see clauseguard_build_conventions memory).
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class DocumentModel(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_path: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AnalysisResultModel(Base):
    """One row per document - a new analysis overwrites the previous result,
    matching the semantics the in-memory store already had (latest result
    wins). The full DocumentAnalysisResult is stored as JSON rather than
    normalized into per-clause rows/columns: the pipeline's output shape
    (nested clauses -> classification/reasoning/findings) changes with the
    pipeline itself, and a JSON blob avoids a migration on every schema
    change to that nested structure - a deliberate, documented trade-off,
    not an oversight."""

    __tablename__ = "analysis_results"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AnalysisJobModel(Base):
    """Backs the async job path (Phase 15's API -> Job creation -> Celery ->
    pipeline -> Postgres path), additive alongside the existing synchronous
    /analyze endpoint - see backend/app/api/routes/jobs.py."""

    __tablename__ = "analysis_jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
