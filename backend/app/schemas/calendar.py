"""Pydantic schemas for calendar OAuth and event endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalendarConnectRequest(BaseModel):
    """Request to initiate an OAuth connection."""

    provider: str = Field(
        ..., description="Calendar provider: 'google' or 'microsoft'"
    )


class CalendarConnectResponse(BaseModel):
    """Response containing the provider's OAuth authorization URL."""

    auth_url: str = Field(..., description="Redirect the user to this URL to authorize")
    provider: str


class CalendarCallbackQuery(BaseModel):
    """Query parameters returned by the OAuth provider callback."""

    code: str
    state: str  # artisan_id encoded as string
    error: str | None = None


class CalendarEventResponse(BaseModel):
    """A single cached calendar event."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artisan_id: int
    provider: str
    external_id: str
    title: str | None
    start_time: datetime
    end_time: datetime
    location: str | None
    latitude: str | None
    longitude: str | None
    is_busy: bool
    synced_at: datetime


class CalendarStatusResponse(BaseModel):
    """Current calendar connection status for the artisan."""

    connected: bool
    providers: list[str] = Field(default_factory=list)
    event_count: int = 0
