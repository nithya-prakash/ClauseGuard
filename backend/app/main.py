from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.environment == "development" else [],
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


app.include_router(health.router)
