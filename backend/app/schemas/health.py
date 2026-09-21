from typing import Literal

from pydantic import BaseModel

DependencyStatus = Literal["ok", "error", "not_configured"]


class DependencyHealth(BaseModel):
    status: DependencyStatus
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: DependencyHealth
    qdrant: DependencyHealth
    redis: DependencyHealth
    llm_reasoning: DependencyHealth
