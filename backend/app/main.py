from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import documents, health
from app.core.config import get_settings
from app.core.exceptions import ClauseGuardError
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(
    title="ClauseGuard",
    description=(
        "AI-assisted first-pass compliance/risk analysis for German contracts. "
        "This system does not provide legal advice and does not determine "
        "whether a contract is legally valid."
    ),
    version="0.1.0",
)

_cors_origins = settings.cors_allowed_origins_list if settings.environment == "development" else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ClauseGuardError)
async def clauseguard_error_handler(request: Request, exc: ClauseGuardError) -> JSONResponse:
    logger.warning(
        "request_failed",
        path=request.url.path,
        error=exc.detail,
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Defense in depth: any exception NOT already raised as a ClauseGuardError
    # (a real gap found during Milestone 12 - a missing runtime file surfaced
    # as an unhandled FileNotFoundError) is logged with full detail server-side
    # but never returns internals (stack trace, file paths, exception type) to
    # the caller.
    logger.error(
        "unhandled_exception", path=request.url.path, error=str(exc), exc_type=type(exc).__name__
    )
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})


app.include_router(health.router)
app.include_router(documents.router)
