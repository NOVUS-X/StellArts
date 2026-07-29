import asyncio
import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from stellar_sdk import TransactionEnvelope

from app.core.auth import require_admin, require_client, require_client_or_artisan
from app.core.config import settings
from app.db.session import get_db
from app.models.booking import Booking
from app.models.client import Client
from app.models.payment import Payment
from app.models.user import User
from app.services import notification_service
from app.services import payments as payments_service
from app.services.payments import (
    prepare_payment,
    refund_payment,
    release_payment,
    submit_signed_payment,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# deprecated: used by the insecure /hold endpoint which has been removed


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


class PaymentHistoryItem(BaseModel):
    id: str
    booking_id: str
    amount: Decimal
    transaction_hash: str | None
    status: str
    asset_code: str
    created_at: str
    service: str | None = None
    counterparty: str | None = None


@router.get("/my-payments", summary="List payment history for current user")
def my_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_or_artisan),
):
    """Return payments associated with the current user's bookings."""
    booking_ids: list[uuid.UUID] = []

    if current_user.role == "client":
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if client:
            booking_ids = [
                row[0]
                for row in db.query(Booking.id)
                .filter(Booking.client_id == client.id)
                .all()
            ]
    elif current_user.role == "artisan":
        from app.models.artisan import Artisan

        artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
        if artisan:
            booking_ids = [
                row[0]
                for row in db.query(Booking.id)
                .filter(Booking.artisan_id == artisan.id)
                .all()
            ]

    if not booking_ids:
        return []

    payments = (
        db.query(Payment)
        .filter(Payment.booking_id.in_(booking_ids))
        .order_by(Payment.created_at.desc())
        .all()
    )

    results: list[PaymentHistoryItem] = []
    for payment in payments:
        booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
        service = booking.service if booking else None
        counterparty = None
        if booking:
            if current_user.role == "client" and booking.artisan:
                counterparty = (
                    booking.artisan.user.full_name
                    if booking.artisan.user
                    else f"Artisan #{booking.artisan_id}"
                )
            elif current_user.role == "artisan" and booking.client:
                counterparty = (
                    booking.client.user.full_name
                    if booking.client.user
                    else f"Client #{booking.client_id}"
                )

        results.append(
            PaymentHistoryItem(
                id=str(payment.id),
                booking_id=str(payment.booking_id),
                amount=payment.amount,
                transaction_hash=payment.transaction_hash,
                status=payment.status.value if payment.status else "pending",
                asset_code=payment.asset_code,
                created_at=payment.created_at.isoformat(),
                service=service,
                counterparty=counterparty,
            )
        )

    return results


# The old /hold endpoint has been removed due to security concerns. Clients
# should use the two-step prepare/submit flow instead.  A request to this path
# will now return 404 (FastAPI simply won't register it).


@router.post("/prepare", summary="Prepare unsigned payment XDR for client signing")
def prepare(
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
def release(
    req: ReleaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    logger.info(
        "Admin %s triggered release for payment %s",
        current_user.id,
        req.booking_id,
    )
    try:
        booking_uuid = uuid.UUID(str(req.booking_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Booking not found") from None

    booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    res = release_payment(db, req.booking_id, req.artisan_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))

    try:
        if booking.artisan and booking.artisan.user_id:
            asyncio.create_task(
                notification_service.create_notification(
                    db=db,
                    user_id=booking.artisan.user_id,
                    type="payment_released",
                    title="Escrow Payment Released",
                    message=f"Escrow payment of {req.amount} XLM released for booking '{booking.service}'.",
                    reference_id=str(booking.id),
                )
            )
    except Exception as e:
        logger.warning(f"Failed to send release notification: {e}")

    return res


@router.post("/refund", summary="Refund escrow to client")
def refund(
    req: RefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    logger.info(
        "Admin %s triggered refund for payment %s",
        current_user.id,
        req.booking_id,
    )
    try:
        booking_uuid = uuid.UUID(str(req.booking_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Booking not found") from None

    booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    res = refund_payment(db, req.booking_id, req.client_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))

    try:
        if booking.client and booking.client.user_id:
            asyncio.create_task(
                notification_service.create_notification(
                    db=db,
                    user_id=booking.client.user_id,
                    type="payment_refunded",
                    title="Escrow Payment Refunded",
                    message=f"Escrow payment of {req.amount} XLM refunded for booking '{booking.service}'.",
                    reference_id=str(booking.id),
                )
            )
    except Exception as e:
        logger.warning(f"Failed to send refund notification: {e}")

    return res
