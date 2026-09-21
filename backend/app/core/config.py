from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, sourced from environment variables.

    See .env.example for the full list of variables and their meaning.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Database (defaults match docker-compose's host-mapped ports, for
    # running the API locally against `docker compose up` infra services)
    database_url: str = "postgresql+psycopg://clauseguard:clauseguard@localhost:5436/clauseguard"

    # Qdrant
    qdrant_url: str = "http://localhost:6339"
    qdrant_collection: str = "legal_corpus_de"

    # Redis / Celery
    redis_url: str = "redis://localhost:6383/0"
    celery_broker_url: str = "redis://localhost:6383/0"
    celery_result_backend: str = "redis://localhost:6383/1"

    # LLM reasoning provider. "none" is a deliberate, honest default: with no
    # provider configured the reasoning stage must return NOT_CONFIGURED
    # rather than fabricate a risk assessment.
    llm_provider: Literal["anthropic", "none"] = "none"
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = "claude-sonnet-5"

    # Uploads
    max_upload_size_mb: int = 20
    upload_allowed_extensions: str = ".pdf,.docx"

    @property
    def upload_allowed_extensions_list(self) -> list[str]:
        raw = self.upload_allowed_extensions.split(",")
        return [ext.strip().lower() for ext in raw if ext.strip()]

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider == "anthropic" and bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
