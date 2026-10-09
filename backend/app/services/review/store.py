"""Persistence for reviewer decisions (one JSON row per document)."""

from datetime import UTC, datetime

from app.core import db as _db
from app.models.document import ReviewDecisionModel


def get_decisions(document_id: str) -> dict[str, dict]:
    with _db.SessionLocal() as session:
        row = session.get(ReviewDecisionModel, document_id)
        return dict(row.decisions_json) if row else {}


def save_decisions(document_id: str, decisions: dict[str, dict]) -> None:
    with _db.SessionLocal() as session:
        session.merge(
            ReviewDecisionModel(
                document_id=document_id,
                decisions_json=decisions,
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()
