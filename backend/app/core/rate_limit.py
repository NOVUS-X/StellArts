"""Rate limiting utilities for the API.

This module wraps ``slowapi`` to provide a single shared ``Limiter`` instance
used across the application.  It is primarily applied to the payment
endpoints (``/prepare``, ``/submit``, ``/release``, ``/refund``) to mitigate
booking_id brute-forcing and prevent spamming the Stellar network.

Failed submissions (ones that raise ``HTTPException`` after a transaction is
rejected by the network) are tracked separately with a tighter limit via
:func:`record_failed_submission` / :func:`check_failed_submission_limit`.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Default key function: client IP (falls back to authenticated user if we want
# to extend later).  Using remote address is sufficient for basic abuse
# protection on these endpoints.
limiter = Limiter(key_func=get_remote_address, headers_enabled=False)


# Per-endpoint limits.  Kept conservative enough to allow legitimate users
# to retry a few times while blocking brute-force / spam attacks.
PREPARE_RATE_LIMIT = "10/minute"
SUBMIT_RATE_LIMIT = "10/minute"
RELEASE_RATE_LIMIT = "10/minute"
REFUND_RATE_LIMIT = "10/minute"

# Tighter limit for *failed* transaction submissions.  If a client produces
# too many failing submissions in a short window they are temporarily
# blocked, because each failure still costs Stellar network resources and
# is a strong signal of abuse.
FAILED_SUBMISSION_MAX = 3
FAILED_SUBMISSION_WINDOW_SECONDS = 60


_failed_submissions: Dict[str, Deque[float]] = defaultdict(deque)


def _prune(dq: Deque[float], window: float) -> None:
    cutoff = time.monotonic() - window
    while dq and dq[0] < cutoff:
        dq.popleft()


def check_failed_submission_limit(request: Request) -> None:
    """Raise ``429`` if the caller has accumulated too many failed submissions.

    Should be called *before* attempting a Stellar submission so that a
    client that has already failed repeatedly is prevented from generating
    further load.
    """
    key = get_remote_address(request)
    dq = _failed_submissions[key]
    _prune(dq, FAILED_SUBMISSION_WINDOW_SECONDS)
    if len(dq) >= FAILED_SUBMISSION_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed payment submissions. "
                "Please wait before retrying."
            ),
        )


def record_failed_submission(request: Request) -> None:
    """Record that this caller just had a failed submission."""
    key = get_remote_address(request)
    dq = _failed_submissions[key]
    _prune(dq, FAILED_SUBMISSION_WINDOW_SECONDS)
    dq.append(time.monotonic())


def reset_failed_submissions() -> None:
    """Testing helper: clear all tracked failures."""
    _failed_submissions.clear()


__all__ = [
    "limiter",
    "RateLimitExceeded",
    "PREPARE_RATE_LIMIT",
    "SUBMIT_RATE_LIMIT",
    "RELEASE_RATE_LIMIT",
    "REFUND_RATE_LIMIT",
    "check_failed_submission_limit",
    "record_failed_submission",
    "reset_failed_submissions",
]
