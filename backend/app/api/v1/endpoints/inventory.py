"""
Inventory endpoints for route-based inventory check feature.

Requirements: 1.1, 3.1, 3.2, 3.3, 3.5, 5.2
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_artisan, require_client
from app.db.session import get_db
from app.models.inventory_check_run import InventoryCheckRun
from app.models.user import User
from app.tasks.inventory_check_task import run_inventory_check_task

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ArtisanLocation(BaseModel):
    lat: float
    lng: float


class InventoryCheckRequest(BaseModel):
    artisan_location: ArtisanLocation
    device_token: str
    corridor_meters: int = 500


class SupplyOverrideRequest(BaseModel):
    client_supplied: bool


class BOMItemResponse(BaseModel):
    id: UUID
    job_id: UUID
    part_number: str
    part_name: str
    quantity: int
    client_supplied: bool
    client_supplied_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/jobs/{job_id}/inventory-check",
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_inventory_check(
    job_id: UUID,
    body: InventoryCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """
    Trigger a route-based inventory check for a job.

    Creates an InventoryCheckRun record and enqueues the Celery task.
    Requirements: 1.1, 5.2
    """
    # Create the run record with status=pending
    run = InventoryCheckRun(
        job_id=job_id,
        route_polyline={},
        corridor_meters=body.corridor_meters,
        status="pending",
        started_at=datetime.now(tz=timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Enqueue the Celery task
    run_inventory_check_task.delay(
        str(job_id),
        {"lat": body.artisan_location.lat, "lng": body.artisan_location.lng},
        body.device_token,
        body.corridor_meters,
    )

    return {"run_id": str(run.id), "status": "pending"}


@router.patch(
    "/jobs/{job_id}/bom-items/{item_id}/supply-override",
    response_model=BOMItemResponse,
)
def update_supply_override(
    job_id: UUID,
    item_id: UUID,
    body: SupplyOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """
    Override the client_supplied flag on a BOM item.

    Sets client_supplied_at to now() when true, null when false.
    Requirements: 3.1, 3.2, 3.5
    """
    # Verify the item belongs to the job
    row = db.execute(
        text(
            "SELECT id, job_id, part_number, part_name, quantity, "
            "client_supplied, client_supplied_at "
            "FROM bom_items WHERE id = :item_id AND job_id = :job_id"
        ),
        {"item_id": str(item_id), "job_id": str(job_id)},
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM item {item_id} not found for job {job_id}",
        )

    # Compute client_supplied_at
    supplied_at = datetime.now(tz=timezone.utc) if body.client_supplied else None

    db.execute(
        text(
            "UPDATE bom_items SET client_supplied = :supplied, "
            "client_supplied_at = :supplied_at "
            "WHERE id = :item_id AND job_id = :job_id"
        ),
        {
            "supplied": body.client_supplied,
            "supplied_at": supplied_at,
            "item_id": str(item_id),
            "job_id": str(job_id),
        },
    )
    db.commit()

    # Fetch updated row
    updated = db.execute(
        text(
            "SELECT id, job_id, part_number, part_name, quantity, "
            "client_supplied, client_supplied_at "
            "FROM bom_items WHERE id = :item_id AND job_id = :job_id"
        ),
        {"item_id": str(item_id), "job_id": str(job_id)},
    ).mappings().first()

    return BOMItemResponse(
        id=updated["id"],
        job_id=updated["job_id"],
        part_number=updated["part_number"],
        part_name=updated["part_name"],
        quantity=updated["quantity"],
        client_supplied=updated["client_supplied"],
        client_supplied_at=updated["client_supplied_at"],
    )


@router.get(
    "/jobs/{job_id}/bom-items",
    response_model=list[BOMItemResponse],
)
def list_bom_items(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Return all BOM items for a job including client_supplied status.

    Requirements: 3.3
    """
    rows = db.execute(
        text(
            "SELECT id, job_id, part_number, part_name, quantity, "
            "client_supplied, client_supplied_at "
            "FROM bom_items WHERE job_id = :job_id "
            "ORDER BY part_name"
        ),
        {"job_id": str(job_id)},
    ).mappings().all()

    return [
        BOMItemResponse(
            id=row["id"],
            job_id=row["job_id"],
            part_number=row["part_number"],
            part_name=row["part_name"],
            quantity=row["quantity"],
            client_supplied=row["client_supplied"],
            client_supplied_at=row["client_supplied_at"],
        )
        for row in rows
    ]
