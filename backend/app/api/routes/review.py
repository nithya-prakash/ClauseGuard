"""Human review of an analysis: list flagged clauses, record CONFIRM / DISMISS / ESCALATE.

Runs the LangGraph triage/review flow (app/services/review/graph.py). The AI risk level is never
changed; decisions are stored next to it. Decisions can be submitted in several requests, and
clauses without one stay UNREVIEWED."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.services.pipeline.store import get_document, get_result
from app.services.review.graph import ReviewedAnalysis, review_reasons, run_review
from app.services.review.store import get_decisions, save_decisions

router = APIRouter(prefix="/documents", tags=["review"])


class ReviewDecision(BaseModel):
    decision: Literal["CONFIRM", "DISMISS", "ESCALATE"]
    note: str | None = Field(default=None, max_length=500)


class ReviewDecisionsRequest(BaseModel):
    decisions: dict[str, ReviewDecision]


def _analysis_or_404(document_id: str):
    if get_document(document_id) is None:
        raise NotFoundError(f"No document with id '{document_id}'.")
    result = get_result(document_id)
    if result is None:
        raise NotFoundError(f"Document '{document_id}' has not been analyzed yet.")
    return result


@router.get("/{document_id}/review", response_model=ReviewedAnalysis)
def get_review(document_id: str) -> ReviewedAnalysis:
    analysis = _analysis_or_404(document_id)
    return run_review(analysis, get_decisions(document_id))


@router.put("/{document_id}/review", response_model=ReviewedAnalysis)
def submit_review(document_id: str, body: ReviewDecisionsRequest) -> ReviewedAnalysis:
    analysis = _analysis_or_404(document_id)
    flagged = {c.clause.clause_id for c in analysis.clauses if review_reasons(c)}
    unknown = sorted(set(body.decisions) - flagged)
    if unknown:
        raise ValidationFailedError(f"Clauses not flagged for review: {', '.join(unknown)}.")
    decisions = get_decisions(document_id)
    decisions.update({cid: d.model_dump() for cid, d in body.decisions.items()})
    save_decisions(document_id, decisions)
    return run_review(analysis, decisions)
