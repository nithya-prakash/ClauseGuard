from pydantic import BaseModel

from app.schemas.classification import ClassificationResult
from app.schemas.clause import Clause
from app.schemas.reasoning import ReasoningResult


class ClauseAnalysis(BaseModel):
    clause: Clause
    classification: ClassificationResult | None
    classification_error: str | None
    reasoning: ReasoningResult | None
    reasoning_error: str | None


class DocumentAnalysisResult(BaseModel):
    filename: str
    analyzed_at: str
    clause_count: int
    clauses: list[ClauseAnalysis]
