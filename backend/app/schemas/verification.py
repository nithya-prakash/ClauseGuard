from typing import Literal

from pydantic import BaseModel

from app.schemas.retrieval import RetrievedPassage

EvidenceStatus = Literal["SUFFICIENT", "INSUFFICIENT_EVIDENCE"]
CitationStatus = Literal["VERIFIED", "CITATION_UNVERIFIED"]


class EvidenceSufficiencyResult(BaseModel):
    status: EvidenceStatus
    reason: str | None
    top_score: float | None
    evidence: list[RetrievedPassage]


class CitationCheckResult(BaseModel):
    citation: str
    status: CitationStatus
    reason: str | None
