# app/api/v1/endpoints/payments.py
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from stellar_sdk import TransactionEnvelope

from app.core.auth import require_client
from app.core.config import settings
from app.db.session import get_db
from app.models.booking import Booking
from app.models.notification import NotificationType
from app.models.payment import PaymentAudit
from app.models.user import User
from app.schemas.payment_audit import (
    PaymentAuditListResponse,
    PaymentAuditResponse,
)
from app.services import payments as payments_service
from app.services.notifications import notification_service as notif_service
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
            detail=("You are not authorized to prepare payment for this booking"),
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

    # Parse XDR locally to resolve booking id and verify ownership
    try:
        tx = TransactionEnvelope.from_xdr(
            req.signed_xdr,
            network_passphrase=payments_service.NETWORK_PASSPHRASE,
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

    # Create notifications for payment release
    try:
        booking_uuid = uuid.UUID(req.booking_id)
        booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
        if booking:
            # Notify artisan that payment was released
            notif_service.create_notification(
                db=db,
                user_id=booking.artisan.user_id,
                notification_type=NotificationType.PAYMENT_RELEASED,
                title="Payment Released!",
                message=(
                    f"Payment of {req.amount} XLM has been released to you "
                    f"for booking: {booking.service}."
                ),
                reference_id=booking.id,
            )
            # Notify client that payment was released
            notif_service.create_notification(
                db=db,
                user_id=booking.client.user_id,
                notification_type=NotificationType.PAYMENT_RELEASED,
                title="Payment Released",
                message=(
                    f"Payment of {req.amount} XLM has been released to the "
                    f"artisan for your booking: {booking.service}."
                ),
                reference_id=booking.id,
            )
    except Exception as e:
        # Log error but don't fail the payment release
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create payment release notification: {e}")

    return res


@router.post("/refund", summary="Refund escrow to client")
def refund(req: RefundRequest, db: Session = Depends(get_db)):
    res = refund_payment(db, req.booking_id, req.client_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))

    # Create notifications for payment refund
    try:
        booking_uuid = uuid.UUID(req.booking_id)
        booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
        if booking:
            # Notify client that payment was refunded
            notif_service.create_notification(
                db=db,
                user_id=booking.client.user_id,
                notification_type=NotificationType.PAYMENT_REFUNDED,
                title="Payment Refunded",
                message=(
                    f"Payment of {req.amount} XLM has been refunded to you "
                    f"for booking: {booking.service}."
                ),
                reference_id=booking.id,
            )
    except Exception as e:
        # Log error but don't fail the payment refund
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create payment refund notification: {e}")

    return res


@router.get(
    "/audits",
    summary="Get payment audit logs",
    response_model=PaymentAuditListResponse,
)
def get_payment_audits(
    booking_id: Optional[str] = Query(None, description="Filter by booking ID"),
    payment_id: Optional[str] = Query(None, description="Filter by payment ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieve payment audit logs for transparency and compliance.

    Audit logs are immutable and provide a complete history of all payment
    lifecycle events including state changes, transaction hashes, and
    timestamps.
    """
    query = db.query(PaymentAudit)

    if booking_id:
        try:
            booking_uuid = uuid.UUID(booking_id)
            query = query.filter(PaymentAudit.booking_id == booking_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")

    if payment_id:
        try:
            payment_uuid = uuid.UUID(payment_id)
            query = query.filter(PaymentAudit.payment_id == payment_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payment ID format")

    # Get total count
    total = query.count()

    # Get paginated results, ordered by creation date (newest first)
    audits = (
        query.order_by(PaymentAudit.created_at.desc()).offset(skip).limit(limit).all()
    )

    return PaymentAuditListResponse(
        audits=[PaymentAuditResponse.from_orm(audit) for audit in audits],
        total=total,
    )


@router.get(
    "/audits/{booking_id}",
    summary="Get payment audit logs for a specific booking",
    response_model=PaymentAuditListResponse,
)
def get_booking_payment_audits(
    booking_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieve all payment audit logs for a specific booking."""
    try:
        booking_uuid = uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")

    # Verify booking exists
    booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    query = db.query(PaymentAudit).filter(PaymentAudit.booking_id == booking_uuid)

    # Get total count
    total = query.count()

    # Get paginated results, ordered by creation date (newest first)
    audits = (
        query.order_by(PaymentAudit.created_at.desc()).offset(skip).limit(limit).all()
    )

    return PaymentAuditListResponse(
        audits=[PaymentAuditResponse.from_orm(audit) for audit in audits],
        total=total,
    )
