"""Milestone 16 Phase 17: a minimal, dependency-free rate limiter for the
expensive per-clause pipeline endpoints (/analyze, POST /jobs - each call
runs classification + retrieval + reranking, and possibly an LLM call, per
clause in the document).

Deliberately simple: a fixed-window counter per client IP, held in an
in-process dict. This is a REAL, disclosed limitation, not hidden: it is
per-process, not shared across multiple backend replicas or restarts, and
trusts the client's reported IP (spoofable behind a misconfigured proxy
without X-Forwarded-For handling). Documented in README's Security section
rather than presented as a complete defense - a production deployment
behind a real load balancer would want a shared store (Redis, which this
project already has) instead. Kept this simple per the spec's own guidance
("add rate limiting if it can be implemented cleanly without unnecessary
complexity") rather than reaching for a new dependency for a portfolio
project's rate limiting.
"""

from collections import defaultdict
from threading import Lock
from time import time

from fastapi import Request

from app.core.exceptions import RateLimitExceededError

MAX_REQUESTS_PER_WINDOW = 10
WINDOW_SECONDS = 60.0

_request_log: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    key = _client_key(request)
    now = time()
    with _lock:
        recent = [t for t in _request_log[key] if now - t < WINDOW_SECONDS]
        if len(recent) >= MAX_REQUESTS_PER_WINDOW:
            _request_log[key] = recent
            raise RateLimitExceededError(
                f"Rate limit exceeded: max {MAX_REQUESTS_PER_WINDOW} requests per "
                f"{int(WINDOW_SECONDS)}s for this endpoint. Try again shortly."
            )
        recent.append(now)
        _request_log[key] = recent


def reset_rate_limits() -> None:
    """Test-only: clears all tracked request history between test cases."""
    with _lock:
        _request_log.clear()
