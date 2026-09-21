from typing import Literal

from fastapi import APIRouter
from sqlalchemy import text

from app.core.clients import get_qdrant_client, get_redis_client
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import get_logger
from app.schemas.health import DependencyHealth, HealthResponse

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


def _check_database() -> DependencyHealth:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return DependencyHealth(status="ok")
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        return DependencyHealth(status="error", detail=str(exc))


def _check_qdrant() -> DependencyHealth:
    try:
        get_qdrant_client().get_collections()
        return DependencyHealth(status="ok")
    except Exception as exc:  # noqa: BLE001
        return DependencyHealth(status="error", detail=str(exc))


def _check_redis() -> DependencyHealth:
    try:
        get_redis_client().ping()
        return DependencyHealth(status="ok")
    except Exception as exc:  # noqa: BLE001
        return DependencyHealth(status="error", detail=str(exc))


def _check_llm() -> DependencyHealth:
    settings = get_settings()
    if settings.llm_configured:
        return DependencyHealth(status="ok")
    return DependencyHealth(
        status="not_configured",
        detail="Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable the reasoning stage.",
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    database = _check_database()
    qdrant = _check_qdrant()
    redis_ = _check_redis()
    llm = _check_llm()

    # llm_reasoning being "not_configured" is expected/healthy in dev without
    # a key; it degrades overall status only if it errored, not if it's
    # simply unconfigured.
    hard_failures = [d for d in (database, qdrant, redis_) if d.status == "error"]
    overall: Literal["ok", "degraded"] = "degraded" if hard_failures else "ok"

    if hard_failures:
        logger.warning("health_check_degraded", failures=[d.detail for d in hard_failures])

    return HealthResponse(
        status=overall,
        database=database,
        qdrant=qdrant,
        redis=redis_,
        llm_reasoning=llm,
    )
