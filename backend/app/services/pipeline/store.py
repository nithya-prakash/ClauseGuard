"""Document/result persistence (Milestone 16 Phase 15).

Was an in-memory dict store through Milestone 15 (lost on restart, not
shared across replicas - see git history for that version). Now backed by
Postgres via SQLAlchemy, so it survives a restart and is shared across
backend/worker processes - the requirement this phase exists to satisfy.

`from app.core import db as _db` (not `from app.core.db import SessionLocal`)
is deliberate: it reads `_db.SessionLocal` at CALL time, not import time, so
the test-tier fixture (backend/tests/conftest.py) can monkeypatch
`app.core.db.SessionLocal` to a fast in-memory SQLite session factory after
this module has already been imported elsewhere in the app, and every call
here picks up the swap - no test needs a real Postgres connection unless
it's explicitly `@pytest.mark.integration`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core import db as _db
from app.models.document import AnalysisResultModel, DocumentModel, ReviewDecisionModel
from app.schemas.pipeline import DocumentAnalysisResult


@dataclass
class DocumentRecord:
    document_id: str
    original_filename: str
    stored_path: Path
    content_type: str


def save_document(record: DocumentRecord) -> None:
    with _db.SessionLocal() as session:
        session.merge(
            DocumentModel(
                document_id=record.document_id,
                original_filename=record.original_filename,
                stored_path=str(record.stored_path),
                content_type=record.content_type,
            )
        )
        session.commit()


def get_document(document_id: str) -> DocumentRecord | None:
    with _db.SessionLocal() as session:
        row = session.get(DocumentModel, document_id)
        if row is None:
            return None
        return DocumentRecord(
            document_id=row.document_id,
            original_filename=row.original_filename,
            stored_path=Path(row.stored_path),
            content_type=row.content_type,
        )


def save_result(document_id: str, result: DocumentAnalysisResult) -> None:
    with _db.SessionLocal() as session:
        session.merge(
            AnalysisResultModel(
                document_id=document_id,
                result_json=result.model_dump(mode="json"),
                analyzed_at=datetime.now(UTC),
            )
        )
        session.commit()


def get_result(document_id: str) -> DocumentAnalysisResult | None:
    with _db.SessionLocal() as session:
        row = session.get(AnalysisResultModel, document_id)
        if row is None:
            return None
        return DocumentAnalysisResult.model_validate(row.result_json)


def delete_document(document_id: str) -> DocumentRecord | None:
    """Removes a document's metadata and analysis result from the store
    (spec section 29: "provide cleanup/delete functionality"). Does not
    touch the file on disk - the caller (the API route) does that, since
    filesystem access doesn't belong in this persistence module."""
    with _db.SessionLocal() as session:
        doc_row = session.get(DocumentModel, document_id)
        if doc_row is None:
            return None
        record = DocumentRecord(
            document_id=doc_row.document_id,
            original_filename=doc_row.original_filename,
            stored_path=Path(doc_row.stored_path),
            content_type=doc_row.content_type,
        )
        result_row = session.get(AnalysisResultModel, document_id)
        if result_row is not None:
            session.delete(result_row)
        review_row = session.get(ReviewDecisionModel, document_id)
        if review_row is not None:
            session.delete(review_row)
        session.delete(doc_row)
        session.commit()
        return record
