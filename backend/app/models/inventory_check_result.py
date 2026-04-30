"""Persisted result of a route-based inventory check for a booking."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.sql import func

from app.db.base import Base


class InventoryCheckResult(Base):
    __tablename__ = "inventory_check_results"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False, index=True)
    # JSON: list of StoreMatch objects returned by InventoryService
    matches_json = Column(Text, nullable=True)
    # True when the client indicated they already have all materials
    client_supplied = Column(Boolean, default=False, nullable=False)
    # Notification sent to artisan?
    notification_sent = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
