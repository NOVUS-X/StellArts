# app/api/v1/endpoints/payments.py
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from stellar_sdk import TransactionEnvelope

from app.core.auth import require_client
from app.core.config import settings
from app.db.session import get_db
from app.models.booking import Booking
from app.models.user import User
from app.services import payments as payments_service
from app.services.email import send_auto_release_email
from app.services.payments import (
    auto_release_milestone_payment,
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


class OracleAutoReleaseRequest(BaseModel):
    booking_id: str
    engagement_id: int = Field(..., gt=0)
    token_address: str = Field(..., min_length=3)
    confidence_score: float = Field(..., ge=0, le=1)
    test_results: dict[str, Any] | list[str] | str


def _serialize_test_results(test_results: dict[str, Any] | list[str] | str) -> str:
    if isinstance(test_results, str):
        return test_results
    if isinstance(test_results, list):
        return "\n".join(f"- {item}" for item in test_results)
    return "\n".join(f"- {key}: {value}" for key, value in test_results.items())


def _require_oracle_token(x_oracle_token: str | None) -> None:
    if not settings.BACKEND_ORACLE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend oracle token is not configured",
        )

    if x_oracle_token != settings.BACKEND_ORACLE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid backend oracle token",
        )


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


@router.post(
    "/oracle/auto-release",
    summary="Auto-release escrow through the backend oracle for high-confidence jobs",
)
def auto_release(
    req: OracleAutoReleaseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_oracle_token: str | None = Header(default=None, alias="X-Oracle-Token"),
):
    _require_oracle_token(x_oracle_token)
    rendered_test_results = _serialize_test_results(req.test_results)
    result = auto_release_milestone_payment(
        db,
        booking_id=req.booking_id,
        engagement_id=req.engagement_id,
        token_address=req.token_address,
        confidence_score=req.confidence_score,
        test_results=rendered_test_results,
        threshold=settings.AUTO_RELEASE_CONFIDENCE_THRESHOLD,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    if result.get("status") in {"success", "exists"}:
        background_tasks.add_task(
            send_auto_release_email,
            to=result["client_email"],
            full_name=result["client_name"],
            booking_id=req.booking_id,
            confidence_score=req.confidence_score,
            transaction_hash=result["transaction_hash"],
            test_results=rendered_test_results,
        )
        result["client_notification"] = {
            "channel": "email",
            "recipient": result["client_email"],
            "delivered_test_results": True,
        }
    else:
        result["client_notification"] = {
            "channel": "email",
            "recipient": None,
            "delivered_test_results": False,
        }

    return result
