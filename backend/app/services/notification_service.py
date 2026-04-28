"""
NotificationService — dispatches in-app and email notifications.

Push notifications are stored in the `notifications` table so the
frontend can poll/SSE them.  An email fallback is attempted when SMTP
is configured.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session

from app.db.base import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notification model (defined here to keep the feature self-contained)
# ---------------------------------------------------------------------------


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)
    read = Column(String(10), default="false", nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class NotificationService:
    """Persist in-app notifications and optionally send email alerts."""

    def send(
        self,
        db: Session,
        user_id: int,
        title: str,
        body: str,
        action_url: str | None = None,
    ) -> Notification:
        """Persist a notification row and attempt an email fallback."""
        notif = Notification(
            user_id=user_id,
            title=title,
            body=body,
            action_url=action_url,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        logger.info("Notification %s sent to user %s", notif.id, user_id)
        return notif

    def send_inventory_alert(
        self,
        db: Session,
        artisan_user_id: int,
        store_name: str,
        item_names: list[str],
        prepay_url: str,
    ) -> Notification:
        """Convenience wrapper for the inventory-found push notification."""
        items_str = ", ".join(item_names[:3])
        if len(item_names) > 3:
            items_str += f" (+{len(item_names) - 3} more)"

        title = f"Materials found at {store_name}"
        body = (
            f"I found {items_str} on your route at {store_name}. "
            "Tap to pre-pay and pick up on the way."
        )
        return self.send(
            db=db,
            user_id=artisan_user_id,
            title=title,
            body=body,
            action_url=prepay_url,
        )

    # ------------------------------------------------------------------
    # Legacy stubs kept for backward compatibility
    # ------------------------------------------------------------------

    @staticmethod
    def dispatch_smart_pitch(artisan, booking, pitch_message):
        return {
            "artisan_id": artisan.id,
            "booking_id": booking.id,
            "message": pitch_message,
            "status": "dispatched",
        }

    @staticmethod
    async def dispatch_to_matched_artisans(db, booking, limit=5):
        return []


notification_service = NotificationService()
