"""
Scheduling / slot-suggestion API endpoint.

Open to both clients (requesting a service) and artisans (checking their
own schedule).  Results are derived from the artisan's synced calendar
events and existing DB bookings.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_client_or_artisan
from app.db.session import get_db
from app.models.artisan import Artisan
from app.models.user import User
from app.schemas.scheduling import SlotSuggestionRequest, SlotSuggestionResponse
from app.services.scheduling import scheduling_service

router = APIRouter(prefix="/scheduling")


@router.post("/suggest", response_model=SlotSuggestionResponse)
async def suggest_slots(
    request: SlotSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_or_artisan),
):
    """
    Suggest optimal booking time slots for an artisan on a given day.

    The engine:
    - Syncs the artisan's calendar (if connected via OAuth) before computing.
    - Filters out any slots that overlap existing calendar events or confirmed
      bookings (double-booking prevention).
    - Scores remaining slots by travel distance from the artisan's last known
      job location (geographic grouping).

    Returns slots sorted best-first (lowest travel = highest score).
    """
    artisan = db.query(Artisan).filter(Artisan.id == request.artisan_id).first()
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artisan {request.artisan_id} not found",
        )

    result = await scheduling_service.suggest_slots(
        request=request,
        artisan=artisan,
        db=db,
    )
    return result
