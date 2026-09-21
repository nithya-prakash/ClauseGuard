import pytest

from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit import (
    MAX_REQUESTS_PER_WINDOW,
    enforce_rate_limit,
    reset_rate_limits,
)


class _FakeClient:
    def __init__(self, host: str):
        self.host = host


class _FakeRequest:
    def __init__(self, host: str):
        self.client = _FakeClient(host)


def test_requests_within_the_limit_are_allowed():
    reset_rate_limits()
    request = _FakeRequest("1.2.3.4")
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        enforce_rate_limit(request)  # must not raise


def test_exceeding_the_limit_raises_429():
    reset_rate_limits()
    request = _FakeRequest("1.2.3.5")
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        enforce_rate_limit(request)
    with pytest.raises(RateLimitExceededError) as exc_info:
        enforce_rate_limit(request)
    assert exc_info.value.status_code == 429


def test_different_clients_have_independent_limits():
    reset_rate_limits()
    a, b = _FakeRequest("10.0.0.1"), _FakeRequest("10.0.0.2")
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        enforce_rate_limit(a)
    enforce_rate_limit(b)  # a different client's budget is untouched


def test_no_client_info_falls_back_to_a_shared_unknown_key_without_crashing():
    reset_rate_limits()
    request = type("R", (), {"client": None})()
    enforce_rate_limit(request)  # must not raise (defensive fallback, not a crash)
