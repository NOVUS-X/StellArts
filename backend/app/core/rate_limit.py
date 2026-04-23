"""Rate limiting configuration for the API.

Uses `slowapi` (a starlette/FastAPI-friendly wrapper around `limits`) to apply
per-endpoint request rate limits.  The limiter key is derived from the
authenticated user (via the Authorization header) when present, falling back to
the remote IP address.  This prevents both anonymous IP-level abuse and
per-token brute-forcing of protected resources such as `booking_id`.

Configured limits intentionally use lower thresholds for failed `/submit`
attempts, where each failure spams the Stellar network.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _rate_limit_key(request: Request) -> str:
    """Return a per-client identifier used to bucket rate limits.

    Prefers the bearer token (so a single attacker cannot trivially bypass by
    rotating source IPs) and falls back to the remote address.
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return get_remote_address(request)


# --- Payment endpoint limits -------------------------------------------------
# These strings use slowapi/limits syntax, e.g. "10/minute".  They are kept as
# module-level constants so tests and other modules can reference them.
PREPARE_RATE_LIMIT = getattr(settings, "RATE_LIMIT_PAYMENTS_PREPARE", "10/minute")
SUBMIT_RATE_LIMIT = getattr(settings, "RATE_LIMIT_PAYMENTS_SUBMIT", "5/minute")
SUBMIT_FAILED_RATE_LIMIT = getattr(
    settings, "RATE_LIMIT_PAYMENTS_SUBMIT_FAILED", "3/minute"
)
RELEASE_RATE_LIMIT = getattr(settings, "RATE_LIMIT_PAYMENTS_RELEASE", "5/minute")
REFUND_RATE_LIMIT = getattr(settings, "RATE_LIMIT_PAYMENTS_REFUND", "5/minute")


# Storage backing for rate-limit counters.  Defaults to in-process memory,
# which is fine for single-worker deployments and tests.  To share limits
# across multiple worker processes, set RATE_LIMIT_STORAGE_URI (e.g. to the
# application's Redis URL).
_storage_uri = getattr(settings, "RATE_LIMIT_STORAGE_URI", None) or "memory://"

# `headers_enabled` is left at its default (False) because the application
# mounts `SlowAPIMiddleware`, which handles RateLimit-* response headers.
limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=_storage_uri,
    default_limits=[],
)


# Separate, lower-level bucket used to track *failed* /submit attempts.
# slowapi's decorator only counts the request itself, so we maintain a
# parallel window here that we manually bump when a submission fails.
try:
    _failed_storage = storage_from_string(_storage_uri)
except Exception:
    _failed_storage = storage_from_string("memory://")

_failed_strategy = MovingWindowRateLimiter(_failed_storage)
_failed_submit_item = parse(SUBMIT_FAILED_RATE_LIMIT)


def _failed_submit_bucket(request: Request) -> str:
    return f"failed-submit:{_rate_limit_key(request)}"


def check_failed_submit_quota(request: Request) -> None:
    """Raise HTTP 429 if this client has exhausted the failed-submit quota.

    Does not consume the quota; call `record_failed_submit` after an attempt
    fails to actually decrement the bucket.
    """
    try:
        allowed = _failed_strategy.test(
            _failed_submit_item, _failed_submit_bucket(request)
        )
    except Exception:
        # If the storage backend is unavailable, fail open rather than denying
        # legitimate traffic.  The primary /submit slowapi limit still applies.
        return
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed payment submissions. Please wait before "
                "retrying."
            ),
        )


def record_failed_submit(request: Request) -> None:
    """Consume one slot in the failed-submit quota.

    Called after a `/submit` call is rejected so repeated failures quickly
    exhaust the stricter limit independently of successful traffic.  Errors
    here are swallowed so rate-limit bookkeeping can never crash a request.
    """
    try:
        _failed_strategy.hit(_failed_submit_item, _failed_submit_bucket(request))
    except Exception:
        pass
