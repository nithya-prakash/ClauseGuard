import os
import socket
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import db as db_module
from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limits
from app.main import app
from app.models.document import Base  # noqa: F401 - registers all models on Base.metadata


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The rate limiter (Milestone 16 Phase 17) tracks request history in a
    module-level dict for the life of the process - without this, tests
    across different test functions would share rate-limit state and could
    fail depending on test execution order/count, not on their own logic."""
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def _test_database(request: pytest.FixtureRequest):
    """Milestone 16 Phase 15: the persistence layer (store.py) now requires a
    real database session - swaps in a throwaway in-memory SQLite database
    for every test EXCEPT ones marked @pytest.mark.integration, so the fast
    unit-test tier (`pytest -m "not integration"`) stays fast and needs no
    running Postgres. Integration tests use the real configured Postgres
    (app.core.db's default engine, pointing at docker-compose or CI's
    service container) so persistence is verified against real infra too -
    not mocked there, per this project's established convention.

    Patches `app.core.db.SessionLocal` (not just `.engine`) because
    store.py reads `db_module.SessionLocal` at call time (see its module
    docstring) - the sessionmaker itself, not just the engine it was built
    from, must be swapped.
    """
    if "integration" in request.keywords:
        Base.metadata.create_all(bind=db_module.engine)
        yield
        return

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    test_session_local = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    original_engine, original_session_local = db_module.engine, db_module.SessionLocal
    db_module.engine = test_engine
    db_module.SessionLocal = test_session_local
    try:
        yield
    finally:
        db_module.engine, db_module.SessionLocal = original_engine, original_session_local
        test_engine.dispose()


def _reachable(url: str, timeout: float = 2.0) -> bool:
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=timeout):
            return True
    except (OSError, TypeError):
        return False


@pytest.fixture(scope="session")
def _integration_services_up() -> bool:
    """Postgres and Qdrant must answer within 2s. Without this, integration tests run on a host
    whose .env points at docker-network names (postgres, qdrant) stall on DNS/connect timeouts
    and look like hangs."""
    settings = get_settings()
    return _reachable(settings.database_url) and _reachable(settings.qdrant_url)


@pytest.fixture(autouse=True)
def _require_services_for_integration(request: pytest.FixtureRequest, _integration_services_up):
    """Skip integration tests quickly when the stack is unreachable. In CI (CI=true) the stack is
    always provisioned, so an unreachable service there is a failure, not a skip."""
    if "integration" not in request.keywords or _integration_services_up:
        return
    message = "Postgres/Qdrant unreachable at DATABASE_URL/QDRANT_URL (see README: running tests)"
    if os.getenv("CI"):
        pytest.fail(message)
    pytest.skip(message)
