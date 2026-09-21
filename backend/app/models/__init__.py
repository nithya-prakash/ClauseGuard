"""Import every model module here so app.core.db.Base.metadata sees all
tables - required for Base.metadata.create_all() (tests) and Alembic
autogenerate (migrations/env.py imports this package)."""

from app.models.document import AnalysisJobModel, AnalysisResultModel, DocumentModel

__all__ = ["AnalysisJobModel", "AnalysisResultModel", "DocumentModel"]
