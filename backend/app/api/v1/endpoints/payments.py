# app/api/v1/endpoints/payments.py
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from limits import parse as parse_limit
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from stellar_sdk import TransactionEnvelope

from app.core.auth import require_client
from app.core.config import settings
from app.core.rate_limit import (
    PAYMENT_PREPARE_LIMIT,
    PAYMENT_REFUND_LIMIT,
    PAYMENT_RELEASE_LIMIT,
    PAYMENT_SUBMIT_FAILED_LIMIT,
    PAYMENT_SUBMIT_LIMIT,
    limiter,
)
from app.db.session import get_db
from app.models.booking import Booking
from app.models.user import User
from app.services import payments as payments_service
from app.services.payments import (
    prepare_payment,
    refund_payment,
    release_payment,
    submit_signed_payment,
)

router = APIRouter()

# Bucket name used for the stricter failed-submit rate limit.
_FAILED_SUBMIT_BUCKET = "payments:submit:failed"


class PrepareRequest(BaseModel):
    booking_id: str
    amount: Decimal = Field(..., gt=0)
    client_public: str
    asset_code: str = "XLM"
    asset_issuer: str | None = None


class SubmitRequest(BaseModel):
    signed_xdr: str


class ReleaseRequest(BaseModel):
    booking_id: str
    artisan_public: str
    amount: Decimal = Field(..., gt=0)


class RefundRequest(BaseModel):
    booking_id: str
    client_public: str
    amount: Decimal = Field(..., gt=0)


def _failed_submit_item():
    return parse_limit(PAYMENT_SUBMIT_FAILED_LIMIT)


def _record_failed_submit(request: Request) -> None:
    """Record a failed submission against the stricter failed-submit bucket.

    Applies a tighter limit on erroring submissions (e.g. invalid XDR, unknown
    booking) to blunt brute-force attempts without punishing legitimate users
    who occasionally fail.
    """
    lim = getattr(request.app.state, "limiter", None)
    if lim is None:
        return
    try:
        key = lim._key_func(request)
        lim._limiter.hit(_failed_submit_item(), _FAILED_SUBMIT_BUCKET, key)
    except Exception:
        # Never let rate-limit bookkeeping break the request flow.
        pass


def _check_failed_submit_quota(request: Request) -> None:
    """Reject further calls when the failed-submit bucket is exhausted."""
    lim = getattr(request.app.state, "limiter", None)
    if lim is None:
        return
    try:
        key = lim._key_func(request)
        allowed = lim._limiter.test(_failed_submit_item(), _FAILED_SUBMIT_BUCKET, key)
    except Exception:
        # If the backend is unavailable, fail open rather than block users.
        return
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed payment submissions. Please wait "
                "before trying again."
            ),
        )


# The old /hold endpoint has been removed due to security concerns. Clients
# should use the two-step prepare/submit flow instead.  A request to this path
# will now return 404 (FastAPI simply won't register it).


@router.post("/prepare", summary="Prepare unsigned payment XDR for client signing")
@limiter.limit(PAYMENT_PREPARE_LIMIT)
def prepare(
    request: Request,
    req: PrepareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    # Reject unsupported assets
    if req.asset_code.upper() not in settings.SUPPORTED_ASSET_CODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Asset code '{req.asset_code}' is not supported. Allowed: {', '.join(settings.SUPPORTED_ASSET_CODES)}",
        )

    # Require verified email before preparing payments (configurable)
    if settings.REQUIRE_EMAIL_VERIFICATION and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Email verification required before preparing payments. "
                "Check your inbox or request a new verification email."
            ),
        )

    # Verify booking exists and belongs to current user
    try:
        b_id = uuid.UUID(req.booking_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Booking not found") from None

    booking = db.query(Booking).filter(Booking.id == b_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.client.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to prepare payment for this booking",
        )

    return prepare_payment(
        req.booking_id,
        req.amount,
        req.client_public,
        req.asset_code,
        req.asset_issuer,
    )


@router.post("/submit", summary="Submit signed payment XDR from wallet")
@limiter.limit(PAYMENT_SUBMIT_LIMIT)
def submit(
    request: Request,
    req: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    # Stricter limit for repeatedly-failing submissions.
    _check_failed_submit_quota(request)

    # Require verified email before submitting payments (configurable)
    if settings.REQUIRE_EMAIL_VERIFICATION and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Email verification required before submitting payments. "
                "Check your inbox or request a new verification email."
            ),
        )

    # Parse XDR locally to resolve booking id and verify ownership before submission
    try:
        tx = TransactionEnvelope.from_xdr(
            req.signed_xdr, network_passphrase=payments_service.NETWORK_PASSPHRASE
        )
        memo_text = tx.transaction.memo.memo_text
        if isinstance(memo_text, bytes):
            memo_text = memo_text.decode()
        booking_token = memo_text.replace("hold-", "")
    except Exception:
        _record_failed_submit(request)
        raise HTTPException(
            status_code=400, detail="Invalid signed transaction XDR"
        ) from None

    booking_id = booking_token
    try:
        uuid.UUID(booking_id)
    except ValueError:
        # Try to resolve short token to full UUID
        candidates = [
            str(row[0])
            for row in db.query(Booking.id).all()
            if str(row[0]).startswith(booking_token)
        ]
        if len(candidates) != 1:
            _record_failed_submit(request)
            raise HTTPException(
                status_code=400,
                detail="Unable to resolve booking from transaction memo",
            ) from None
        booking_id = candidates[0]

    # booking_id may be a string; convert to UUID for DB query
    try:
        booking_uuid = uuid.UUID(str(booking_id))
    except ValueError:
        _record_failed_submit(request)
        raise HTTPException(status_code=404, detail="Booking not found") from None

    booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
    if not booking:
        _record_failed_submit(request)
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.client.user_id != current_user.id:
        _record_failed_submit(request)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to submit payment for this booking",
        )

    res = submit_signed_payment(db, req.signed_xdr)
    if res.get("status") == "error":
        _record_failed_submit(request)
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@router.post("/release", summary="Release escrow to artisan")
@limiter.limit(PAYMENT_RELEASE_LIMIT)
def release(request: Request, req: ReleaseRequest, db: Session = Depends(get_db)):
    res = release_payment(db, req.booking_id, req.artisan_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@router.post("/refund", summary="Refund escrow to client")
@limiter.limit(PAYMENT_REFUND_LIMIT)
def refund(request: Request, req: RefundRequest, db: Session = Depends(get_db)):
    res = refund_payment(db, req.booking_id, req.client_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res
