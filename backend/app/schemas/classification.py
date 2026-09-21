from pydantic import BaseModel


class ClassificationResult(BaseModel):
    clause_type: str
    confidence: float
    model_name: str
