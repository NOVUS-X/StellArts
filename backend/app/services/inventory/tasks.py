"""Background task: run inventory check when a booking transitions to IN_PROGRESS."""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.bom import BOMItem
from app.models.booking import Booking
from app.services.inventory.checker import InventoryCheckerService
from app.services.notification_service import notification_service
from app.services.route_service import route_service

logger = logging.getLogger(__name__)


async def run_inventory_check(booking_id: UUID, db: Session) -> None:
    """Async background task that performs the full inventory check pipeline.

    Never raises — all errors are caught and logged.
    """
    try:
        # Load booking
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            logger.warning("run_inventory_check: booking %s not found", booking_id)
            return

        # Req 3.2 / 3.6: skip entirely when client has supplied materials
        if booking.client_supply_override:
            logger.info(
                "run_inventory_check: skipping booking %s — client_supply_override=True",
                booking_id,
            )
            return

        # Load BOM items
        bom_items = db.query(BOMItem).filter(BOMItem.booking_id == booking_id).all()
        if not bom_items:
            logger.info(
                "run_inventory_check: no BOM items for booking %s — skipping",
                booking_id,
            )
            return

        # Get artisan coordinates (Req 1.5: log and skip if unavailable)
        artisan = booking.artisan
        artisan_lat = artisan.latitude if artisan else None
        artisan_lon = artisan.longitude if artisan else None

        if artisan_lat is None or artisan_lon is None:
            logger.warning(
                "run_inventory_check: artisan has no coordinates for booking %s — skipping",
                booking_id,
            )
            return

        artisan_lat = float(artisan_lat)
        artisan_lon = float(artisan_lon)

        # Job site coordinates — use 0.0 placeholder if not parseable
        job_lat, job_lon = 0.0, 0.0
        if booking.location:
            try:
                parts = booking.location.split(",")
                if len(parts) >= 2:
                    job_lat = float(parts[0].strip())
                    job_lon = float(parts[1].strip())
            except (ValueError, AttributeError):
                logger.warning(
                    "run_inventory_check: could not parse location '%s' for booking %s",
                    booking.location,
                    booking_id,
                )

        # Compute route corridor
        corridor = route_service.compute_corridor(artisan_lat, artisan_lon, job_lat, job_lon)

        # Run inventory check (no real adapters wired yet — added in later tasks)
        checker = InventoryCheckerService(adapters=[], cache=None)
        results = await checker.run_check(booking_id, bom_items, corridor, db)

        # Send notifications if artisan has a device token
        if booking.artisan_device_token:
            artisan_id = artisan.id if artisan else None
            await notification_service.send_batch(
                booking.artisan_device_token,
                results,
                booking_id,
                db,
                artisan_id,
            )

        db.commit()

    except Exception:
        logger.exception(
            "run_inventory_check: unhandled error for booking %s", booking_id
        )
