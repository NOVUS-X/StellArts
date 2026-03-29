from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_active_user,
    require_client,
    require_client_or_artisan,
)
from app.db.session import get_db
from app.models.booking import Booking
from app.models.sow import SOW, SOWStatus
from app.schemas.sow import SOWCreate, SOWResponse, SOWFeedback, SOWApprove
from app.services.ai_service import ai_service

router = APIRouter(prefix="/sows")


@router.post(
    "/generate", response_model=SOWResponse, status_code=status.HTTP_201_CREATED
)
def generate_sow(
    payload: SOWCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_client_or_artisan),
):
    """
    Generate a draft SOW by combining Issue-12 output with the user's voice intent.
    Saves a versioned draft SOW attached to a booking.
    """
    # Verify booking exists
    booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Generate SOW markdown
    sow_md = ai_service.generate_sow(payload.issue12_output, payload.user_voice_intent)

    new_sow = SOW(
        booking_id=payload.booking_id,
        content=sow_md,
        status=SOWStatus.DRAFT,
        version=1,
        created_by=getattr(current_user, "id", None),
    )

    db.add(new_sow)
    db.commit()
    db.refresh(new_sow)

    return new_sow


@router.get("/booking/{booking_id}", response_model=list[SOWResponse])
def get_sows_for_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    sows = (
        db.query(SOW)
        .filter(SOW.booking_id == booking_id)
        .order_by(SOW.version.desc())
        .all()
    )
    return sows


@router.put("/{sow_id}/feedback", response_model=SOWResponse)
def provide_feedback(
    sow_id: UUID,
    payload: SOWFeedback,
    db: Session = Depends(get_db),
    current_user=Depends(require_client_or_artisan),
):
    sow = db.query(SOW).filter(SOW.id == sow_id).first()
    if not sow:
        raise HTTPException(status_code=404, detail="SOW not found")

    if sow.status == SOWStatus.FINALIZED:
        raise HTTPException(
            status_code=400, detail="SOW is finalized and cannot be edited"
        )

    # Use AI service to refine the SOW
    refined = ai_service.refine_sow(sow.content, payload.feedback)
    sow.content = refined
    sow.version = (sow.version or 1) + 1
    db.commit()
    db.refresh(sow)

    return sow


@router.post("/{sow_id}/approve")
def approve_sow(
    sow_id: UUID,
    payload: SOWApprove,
    db: Session = Depends(get_db),
    current_user=Depends(require_client),
):
    """
    Approve and finalize the SOW. Only clients may approve.
    Once approved, the SOW is frozen and cannot be changed.
    """
    sow = db.query(SOW).filter(SOW.id == sow_id).first()
    if not sow:
        raise HTTPException(status_code=404, detail="SOW not found")

    if sow.status == SOWStatus.FINALIZED:
        return {"status": "already_finalized", "sow_id": str(sow.id)}

    sow.status = SOWStatus.FINALIZED
    sow.version = (sow.version or 1) + 1
    db.commit()
    db.refresh(sow)

    # Optionally, set a booking field or notify the system. For now, return success.
    return {"status": "finalized", "sow_id": str(sow.id)}
