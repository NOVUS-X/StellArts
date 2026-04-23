"""Rate limiting configuration for sensitive endpoints.

This module exposes a shared ``Limiter`` instance (powered by ``slowapi``) that
is used to protect payment-related endpoints from abuse such as brute-forcing
``booking_id`` values or spamming the Stellar network with failed submissions.

The limiter is keyed by the authenticated user id when available and falls
back to the remote client address otherwise.

Two classes of limits are exposed:

* :data:`PAYMENT_LIMIT` – normal limit for successful/standard calls to
  ``/prepare``, ``/submit`` and ``/release``.
* :data:`PAYMENT_FAILURE_LIMIT` – stricter limit applied on submissions that
  resulted in a failed Stellar transaction. It is enforced manually by the
  submit endpoint after a failure, so repeated failing attempts get blocked
  well before the normal limit is exhausted.
"""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Default per-endpoint limit for normal payment flow calls.
PAYMENT_LIMIT = "10/minute"

# Stricter limit applied to failed /submit calls to avoid spamming the Stellar
# network with broken/invalid transactions.
PAYMENT_FAILURE_LIMIT = "3/minute"


def _key_func(request: Request) -> str:
    """Prefer the authenticated user id when present, else fall back to IP."""
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None) is not None:
        return f"user:{user.id}"
    return get_remote_address(request)


# Allow disabling the limiter in test/CI environments where repeated calls
# from the same client would otherwise exhaust the quota.
_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
    "off",
}

limiter = Limiter(key_func=_key_func, default_limits=[], enabled=_enabled)
