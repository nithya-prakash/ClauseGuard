from pydantic import BaseModel

from app.schemas.pipeline import DocumentAnalysisResult


class AnalysisJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    error: str | None = None
    result: DocumentAnalysisResult | None = None
