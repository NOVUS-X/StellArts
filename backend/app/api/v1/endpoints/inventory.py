from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_client, get_current_active_user
from app.db.session import get_db
from app.models.booking import Booking, BookingStatus
from app.models.client import Client
from app.models.inventory import InventoryCheckResult
from app.models.user import User
from app.schemas.booking import BookingResponse
from app.schemas.inventory import ClientSupplyOverrideRequest, InventoryCheckResultResponse

router = APIRouter()

_STALE_THRESHOLD = timedelta(hours=24)


@router.get("/inventory/{booking_id}/results", response_model=list[InventoryCheckResultResponse])
def get_inventory_results(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return inventory check results for a booking. Staleness is computed at query time."""
    rows = (
        db.query(InventoryCheckResult)
        .filter(InventoryCheckResult.booking_id == booking_id)
        .all()
    )

    now = datetime.now(timezone.utc)
    results = []
    for row in rows:
        checked_at = row.checked_at
        # Ensure timezone-aware comparison
        if checked_at is not None and checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)

        computed_status = row.status
        if checked_at is not None and checked_at < now - _STALE_THRESHOLD:
            computed_status = "stale"

        results.append(
            InventoryCheckResultResponse(
                id=row.id,
                booking_id=row.booking_id,
                bom_item_id=row.bom_item_id,
                store_id=row.store_id,
                store_name=row.store_name,
                store_address=row.store_address,
                available=row.available,
                pre_pay_url=row.pre_pay_url,
                status=computed_status,
                checked_at=row.checked_at,
            )
        )

    return results


@router.post("/bookings/{booking_id}/supply-override", response_model=BookingResponse)
def set_supply_override(
    booking_id: UUID,
    payload: ClientSupplyOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """Set client_supply_override on a booking. Caller must be the booking owner."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Verify caller is the booking owner via their client profile
    client = db.query(Client).filter(Client.user_id == current_user.id).first()
    if not client or booking.client_id != client.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the booking owner")

    # Only allow override on PENDING or CONFIRMED bookings
    if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supply override only allowed on pending or confirmed bookings",
        )

    booking.client_supply_override = payload.client_supply_override
    db.commit()
    db.refresh(booking)
    return booking
