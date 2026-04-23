"""Rate limiting configuration using slowapi.

This module centralises the ``Limiter`` instance used to protect sensitive
endpoints (currently the payment flow) from brute-force ``booking_id``
enumeration and Stellar-network spam.

Limits can be overridden via environment variables so operators can tune
the values without a code change.
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request


def _user_or_ip(request: Request) -> str:
    """Key rate limits by authenticated user id when available, else client IP.

    This prevents a single malicious user from evading per-IP limits by
    rotating IPs when authenticated, and prevents shared NATs from all being
    counted together when users are logged in.
    """
    user = getattr(request.state, "user", None)
    if user is not None:
        user_id = getattr(user, "id", None)
        if user_id is not None:
            return f"user:{user_id}"
    # Authorization header fallback so requests with a JWT that hasn't been
    # resolved yet still bucket per-token rather than per-IP.
    auth = request.headers.get("authorization")
    if auth:
        return f"auth:{auth}"
    return get_remote_address(request)


# Default limits (overridable via env vars).
PAYMENT_PREPARE_LIMIT: str = os.getenv("RATE_LIMIT_PAYMENT_PREPARE", "10/minute")
PAYMENT_SUBMIT_LIMIT: str = os.getenv("RATE_LIMIT_PAYMENT_SUBMIT", "5/minute")
PAYMENT_SUBMIT_FAILED_LIMIT: str = os.getenv(
    "RATE_LIMIT_PAYMENT_SUBMIT_FAILED", "3/minute"
)
PAYMENT_RELEASE_LIMIT: str = os.getenv("RATE_LIMIT_PAYMENT_RELEASE", "10/minute")
PAYMENT_REFUND_LIMIT: str = os.getenv("RATE_LIMIT_PAYMENT_REFUND", "10/minute")


# headers_enabled=False because several endpoints return plain dicts rather
# than Response objects; slowapi's header-injection helper only accepts a
# starlette Response. The SlowAPIMiddleware still enforces the limits.
limiter = Limiter(key_func=_user_or_ip, headers_enabled=False)

__all__ = [
    "limiter",
    "RateLimitExceeded",
    "PAYMENT_PREPARE_LIMIT",
    "PAYMENT_SUBMIT_LIMIT",
    "PAYMENT_SUBMIT_FAILED_LIMIT",
    "PAYMENT_RELEASE_LIMIT",
    "PAYMENT_REFUND_LIMIT",
]
