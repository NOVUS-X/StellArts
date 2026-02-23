# app/api/v1/endpoints/payments.py
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from stellar_sdk import TransactionEnvelope

from app.core.auth import require_client
from app.core.config import settings
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

# deprecated: used by the insecure /hold endpoint which has been removed


class PrepareRequest(BaseModel):
    booking_id: str
    amount: Decimal = Field(..., gt=0)
    client_public: str


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


# The old /hold endpoint has been removed due to security concerns. Clients
# should use the two-step prepare/submit flow instead.  A request to this path
# will now return 404 (FastAPI simply won't register it).


@router.post("/prepare", summary="Prepare unsigned payment XDR for client signing")
def prepare(
    req: PrepareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
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

    return prepare_payment(req.booking_id, req.amount, req.client_public)


@router.post("/submit", summary="Submit signed payment XDR from wallet")
def submit(
    req: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
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
            raise HTTPException(
                status_code=400,
                detail="Unable to resolve booking from transaction memo",
            ) from None
        booking_id = candidates[0]

    # booking_id may be a string; convert to UUID for DB query
    try:
        booking_uuid = uuid.UUID(str(booking_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Booking not found") from None

    booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.client.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to submit payment for this booking",
        )

    res = submit_signed_payment(db, req.signed_xdr)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@router.post("/release", summary="Release escrow to artisan")
def release(req: ReleaseRequest, db: Session = Depends(get_db)):
    res = release_payment(db, req.booking_id, req.artisan_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@router.post("/refund", summary="Refund escrow to client")
def refund(req: RefundRequest, db: Session = Depends(get_db)):
    res = refund_payment(db, req.booking_id, req.client_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res
