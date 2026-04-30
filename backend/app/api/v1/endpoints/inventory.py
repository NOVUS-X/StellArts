"""
Route-based inventory check endpoint.

POST /bookings/{booking_id}/inventory-check

Checks stores along the artisan's route to the job site for required
materials (BOM), persists the result, and sends a push notification to
the artisan for each store that has matching stock.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_artisan
from app.db.session import get_db
from app.models.artisan import Artisan
from app.models.booking import Booking
from app.models.client import Client
from app.models.inventory_check_result import InventoryCheckResult
from app.models.user import User
from app.services.inventory_service import BOMItem, InventoryService
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class BOMItemIn(BaseModel):
    sku: str = Field(..., description="Stock-keeping unit identifier")
    name: str = Field(..., description="Human-readable material name")
    quantity_needed: int = Field(1, ge=1)


class InventoryCheckRequest(BaseModel):
    artisan_lat: float = Field(..., ge=-90, le=90)
    artisan_lon: float = Field(..., ge=-180, le=180)
    job_lat: float = Field(..., ge=-90, le=90)
    job_lon: float = Field(..., ge=-180, le=180)
    bom: list[BOMItemIn] = Field(..., min_length=1, description="Bill of Materials")
    corridor_meters: float = Field(
        500.0, ge=50, le=5000, description="Route corridor width in metres"
    )
    client_supplied: bool = Field(
        False,
        description="Set True if the client already has all required materials",
    )


class StoreMatchOut(BaseModel):
    store_id: str
    store_name: str
    store_address: str
    distance_meters: float
    items_found: list[dict]
    prepay_url: str


class InventoryCheckResponse(BaseModel):
    booking_id: UUID
    client_supplied: bool
    matches: list[StoreMatchOut]
    notifications_sent: int
    check_result_id: UUID


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/bookings/{booking_id}/inventory-check",
    response_model=InventoryCheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["inventory"],
    summary="Check stores along artisan route for required materials",
)
async def check_inventory_along_route(
    booking_id: UUID,
    payload: InventoryCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cross-reference the booking's Bill of Materials with stores located
    along the artisan's route from their current position to the job site.

    - Inventory checks are geographically constrained to the mapped route
      corridor (default ±500 m).
    - A push notification is sent to the artisan for every store that has
      matching stock, with a pre-pay deep-link.
    - If `client_supplied` is True the check is skipped and an empty result
      is returned immediately.
    """
    # --- Authorisation: artisan assigned to this booking, or the client, or admin ---
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    artisan_record = (
        db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
    )
    client_record = db.query(Client).filter(Client.user_id == current_user.id).first()

    is_assigned_artisan = artisan_record and booking.artisan_id == artisan_record.id
    is_booking_client = client_record and booking.client_id == client_record.id
    is_admin = current_user.role == "admin"

    if not (is_assigned_artisan or is_booking_client or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to check inventory for this booking",
        )

    # --- Run inventory check ---
    bom = [
        BOMItem(sku=i.sku, name=i.name, quantity_needed=i.quantity_needed)
        for i in payload.bom
    ]

    svc = InventoryService(db)
    matches = svc.check_route(
        artisan_lat=payload.artisan_lat,
        artisan_lon=payload.artisan_lon,
        job_lat=payload.job_lat,
        job_lon=payload.job_lon,
        bom=bom,
        corridor_meters=payload.corridor_meters,
        client_supplied=payload.client_supplied,
    )

    # --- Persist result ---
    check_result = InventoryCheckResult(
        booking_id=booking_id,
        matches_json=json.dumps([asdict(m) for m in matches]),
        client_supplied=payload.client_supplied,
        notification_sent=False,
    )
    db.add(check_result)
    db.flush()  # get the id before commit

    # --- Send notifications to artisan ---
    notifications_sent = 0
    if matches and artisan_record:
        for match in matches:
            item_names = [
                i.get("name", i.get("sku", "item")) for i in match.items_found
            ]
            try:
                notification_service.send_inventory_alert(
                    db=db,
                    artisan_user_id=artisan_record.user_id,
                    store_name=match.store_name,
                    item_names=item_names,
                    prepay_url=match.prepay_url,
                )
                notifications_sent += 1
            except Exception:
                logger.exception(
                    "Failed to send inventory notification for store %s", match.store_id
                )

        check_result.notification_sent = notifications_sent > 0

    db.commit()
    db.refresh(check_result)

    return InventoryCheckResponse(
        booking_id=booking_id,
        client_supplied=payload.client_supplied,
        matches=[StoreMatchOut(**asdict(m)) for m in matches],
        notifications_sent=notifications_sent,
        check_result_id=check_result.id,
    )


# ---------------------------------------------------------------------------
# Notification read endpoint (artisan polls for their alerts)
# ---------------------------------------------------------------------------


@router.get(
    "/notifications",
    tags=["inventory"],
    summary="Get unread inventory notifications for the current artisan",
)
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    from app.services.notification_service import Notification

    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "action_url": n.action_url,
            "read": n.read,
            "created_at": n.created_at,
        }
        for n in notifs
    ]
