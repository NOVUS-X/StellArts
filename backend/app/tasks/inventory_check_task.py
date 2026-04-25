"""
Celery task: run_inventory_check_task

Orchestrates RoutingService → InventoryService → NotificationService for a
single job's route-based inventory check.

Requirements: 1.1, 1.4, 5.2, 5.3
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

import celery

from app.db.base import SessionLocal
from app.models.inventory_check_run import InventoryCheckRun
from app.services.routing_service import Coordinate, RoutingError, RoutingService
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = celery.Celery("inventory_tasks", broker=_BROKER_URL)

# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=0)
def run_inventory_check_task(
    self,
    job_id: str,
    artisan_location: dict,
    device_token: str,
    corridor_meters: int = 500,
) -> dict | None:
    """
    Orchestrate a full route-based inventory check for *job_id*.

    Parameters
    ----------
    job_id:
        String UUID of the job to check.
    artisan_location:
        Dict with ``{"lat": float, "lng": float}`` representing the artisan's
        current GPS position.
    device_token:
        FCM / Web Push device registration token for the artisan.
    corridor_meters:
        Lateral buffer around the route polyline in metres (default 500).

    Lifecycle
    ---------
    1. Creates an ``InventoryCheckRun`` record with ``status="pending"``.
    2. Calls ``RoutingService.compute_route()``.
       - On ``RoutingError`` (GPS unavailable / provider failure): updates run
         to ``status="failed"``, logs, and returns without querying stores
         (Requirements 1.4, 5.3).
    3. Checks for a newer run for the same job (cancellation support).
       If a newer run exists, marks this run as ``status="failed"`` and exits
       (Requirement 5.2).
    4. Calls ``InventoryService.run_inventory_check()``.
    5. Calls ``NotificationService.send_inventory_alerts()``.
    6. Updates run to ``status="completed"`` with a ``result_summary``.
    7. On any unexpected exception: updates run to ``status="failed"`` and
       re-raises so Celery records the failure.

    Returns
    -------
    dict | None
        A summary dict on success, or ``None`` when the task exits early
        (routing error or cancellation).
    """
    job_uuid = UUID(job_id)

    with SessionLocal() as db:
        # ------------------------------------------------------------------
        # Step 1 — create InventoryCheckRun record (status=pending)
        # ------------------------------------------------------------------
        run = InventoryCheckRun(
            job_id=job_uuid,
            route_polyline={},          # filled in after routing succeeds
            corridor_meters=corridor_meters,
            status="pending",
            started_at=datetime.now(tz=timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

        try:
            # --------------------------------------------------------------
            # Step 2 — compute route
            # --------------------------------------------------------------
            origin = Coordinate(
                latitude=artisan_location["lat"],
                longitude=artisan_location["lng"],
            )

            routing_service = RoutingService()
            try:
                route = asyncio.run(
                    routing_service.compute_route(origin=origin, destination=_job_destination(db, job_uuid))
                )
            except RoutingError as exc:
                logger.error(
                    "RoutingError for job %s (run %s): %s — aborting inventory check",
                    job_id,
                    run_id,
                    exc,
                )
                run.status = "failed"
                run.completed_at = datetime.now(tz=timezone.utc)
                db.commit()
                return None

            # Store the resolved polyline on the run record
            run.route_polyline = route.polyline
            db.commit()

            # --------------------------------------------------------------
            # Step 3 — cancellation check (re-route support, Requirement 5.2)
            # A newer run for the same job means this task has been superseded.
            # --------------------------------------------------------------
            newer_exists = (
                db.query(InventoryCheckRun)
                .filter(
                    InventoryCheckRun.job_id == job_uuid,
                    InventoryCheckRun.id != run_id,
                    InventoryCheckRun.started_at > run.started_at,
                )
                .first()
            )
            if newer_exists:
                logger.info(
                    "Run %s for job %s superseded by newer run %s — cancelling",
                    run_id,
                    job_id,
                    newer_exists.id,
                )
                run.status = "failed"
                run.completed_at = datetime.now(tz=timezone.utc)
                run.result_summary = {"cancelled": True, "reason": "superseded_by_reroute"}
                db.commit()
                return None

            # --------------------------------------------------------------
            # Step 4 — inventory check
            # --------------------------------------------------------------
            inventory_service = InventoryService(db)
            inventory_result = asyncio.run(
                inventory_service.run_inventory_check(
                    job_id=job_uuid,
                    route=route,
                    corridor_meters=corridor_meters,
                )
            )

            # --------------------------------------------------------------
            # Step 5 — send notifications
            # --------------------------------------------------------------
            notification_service = NotificationService()
            notification_results = asyncio.run(
                notification_service.send_inventory_alerts(
                    artisan_id=_artisan_id_for_job(db, job_uuid),
                    matches=inventory_result.matches,
                    started_at=run.started_at,
                    device_token=device_token,
                )
            )

            # --------------------------------------------------------------
            # Step 6 — mark completed
            # --------------------------------------------------------------
            result_summary = {
                "stores_queried": inventory_result.stores_queried,
                "stores_unavailable": inventory_result.stores_unavailable,
                "matches_found": len(inventory_result.matches),
                "notifications_sent": sum(
                    1 for r in notification_results if r.status == "sent"
                ),
            }
            run.status = "completed"
            run.completed_at = datetime.now(tz=timezone.utc)
            run.result_summary = result_summary
            db.commit()

            logger.info(
                "Inventory check completed for job %s (run %s): %s",
                job_id,
                run_id,
                result_summary,
            )
            return result_summary

        except Exception as exc:
            # ----------------------------------------------------------------
            # Step 7 — unexpected failure
            # ----------------------------------------------------------------
            logger.exception(
                "Unexpected error in inventory check for job %s (run %s): %s",
                job_id,
                run_id,
                exc,
            )
            try:
                run.status = "failed"
                run.completed_at = datetime.now(tz=timezone.utc)
                db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to update run %s to failed status", run_id)
            raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_destination(db, job_uuid: UUID) -> Coordinate:
    """
    Retrieve the job-site coordinate for *job_uuid* from the database.

    Queries the ``jobs`` table for ``site_latitude`` / ``site_longitude``
    columns.  Raises ``RoutingError`` if the job is not found or lacks
    location data.
    """
    from sqlalchemy import text

    row = db.execute(
        text("SELECT site_latitude, site_longitude FROM jobs WHERE id = :id"),
        {"id": str(job_uuid)},
    ).mappings().first()

    if row is None:
        raise RoutingError(f"Job {job_uuid} not found")

    lat = row.get("site_latitude")
    lng = row.get("site_longitude")
    if lat is None or lng is None:
        raise RoutingError(f"Job {job_uuid} has no site location")

    return Coordinate(latitude=float(lat), longitude=float(lng))


def _artisan_id_for_job(db, job_uuid: UUID) -> UUID:
    """
    Return the artisan UUID assigned to *job_uuid*.

    Falls back to a nil UUID when the column is absent so that notification
    logging still works even in environments with a minimal jobs schema.
    """
    from sqlalchemy import text

    row = db.execute(
        text("SELECT artisan_id FROM jobs WHERE id = :id"),
        {"id": str(job_uuid)},
    ).mappings().first()

    if row is None or row.get("artisan_id") is None:
        return UUID(int=0)

    return UUID(str(row["artisan_id"]))
