from __future__ import annotations

import json
import logging
import math
from typing import Any

from sqlalchemy.orm import Session

from app.core.websocket import manager
from app.models.artisan import Artisan
from app.models.notification import Notification

logger = logging.getLogger(__name__)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _specialties(value: str | None) -> set[str]:
    if not value:
        return set()
    try:
        parsed = json.loads(value)
        return {str(item).strip().lower() for item in parsed if str(item).strip()}
    except (TypeError, json.JSONDecodeError):
        return {part.strip().lower() for part in value.split(",") if part.strip()}


async def create_notification(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    message: str,
    reference_id: str | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        reference_id=str(reference_id) if reference_id is not None else None,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    payload = {
        "id": str(notification.id),
        "user_id": notification.user_id,
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "read": notification.is_read,
        "reference_id": notification.reference_id,
        "created_at": notification.created_at.isoformat()
        if notification.created_at
        else None,
        "updated_at": notification.updated_at.isoformat()
        if notification.updated_at
        else None,
    }
    try:
        await manager.send_personal_message(payload, user_id)
    except Exception as exc:
        logger.warning(
            "Could not send realtime notification to user %s: %s", user_id, exc
        )
    return notification


async def dispatch_to_matched_artisans(
    db: Session,
    booking: Any,
    latitude: float | None = None,
    longitude: float | None = None,
    limit: int = 5,
) -> list[int]:
    """Notify the five highest-rated available artisans matching the job within 10 km."""
    tags = _specialties(getattr(booking, "job_specialties", None))
    artisans = db.query(Artisan).filter(Artisan.is_available.is_(True)).all()
    candidates: list[tuple[Artisan, float]] = []
    for artisan in artisans:
        artisan_tags = _specialties(artisan.specialties)
        if tags and not tags.intersection(artisan_tags):
            continue
        if latitude is not None and longitude is not None:
            if artisan.latitude is None or artisan.longitude is None:
                continue
            distance = _distance_km(
                latitude, longitude, float(artisan.latitude), float(artisan.longitude)
            )
            if distance > 10:
                continue
        else:
            distance = 0.0
        candidates.append((artisan, distance))

    candidates.sort(
        key=lambda item: (
            -(float(item[0].rating or 0)),
            item[1],
            -(item[0].total_reviews or 0),
        )
    )
    selected = candidates[:limit]
    notified_ids: list[int] = []
    for artisan, distance in selected:
        if not artisan.user_id:
            continue
        await create_notification(
            db=db,
            user_id=artisan.user_id,
            type="booking_created",
            title="New Job Matching Your Skills",
            message=f"A new {', '.join(sorted(tags)) or 'home-service'} request is available {distance:.1f} km away: '{booking.service}'.",
            reference_id=str(booking.id),
        )
        notified_ids.append(artisan.id)
    return notified_ids
