"""
SQLAlchemy models for calendar integration.

ArtisanCalendarToken – stores OAuth tokens per artisan per provider.
CalendarEvent        – local read-only cache of synced calendar events.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.sql import func

from app.db.base import Base


class ArtisanCalendarToken(Base):
    """Stores OAuth refresh/access tokens for a connected calendar provider."""

    __tablename__ = "artisan_calendar_tokens"

    id = Column(Integer, primary_key=True, index=True)
    artisan_id = Column(Integer, ForeignKey("artisans.id"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)  # 'google' | 'microsoft'
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    scope = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CalendarEvent(Base):
    """Read-only local cache of calendar events fetched from connected providers."""

    __tablename__ = "calendar_events"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    artisan_id = Column(Integer, ForeignKey("artisans.id"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)  # 'google' | 'microsoft'
    external_id = Column(String(500), nullable=False)  # provider's event id
    title = Column(String(500), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    location = Column(Text, nullable=True)
    latitude = Column(String(20), nullable=True)   # stored as string for portability
    longitude = Column(String(20), nullable=True)
    is_busy = Column(Boolean, default=True)        # free vs busy events
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
