"""Pydantic schemas for the scheduling / slot-suggestion endpoint."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SlotSuggestionRequest(BaseModel):
    """Parameters needed to suggest optimal booking slots for an artisan."""

    artisan_id: int = Field(..., description="ID of the artisan to schedule")
    client_lat: float = Field(..., description="Client job latitude")
    client_lon: float = Field(..., description="Client job longitude")
    service_duration_hours: float = Field(
        ..., gt=0, description="Estimated service duration in hours"
    )
    preferred_date: datetime = Field(
        ..., description="Preferred date (time component ignored – full day is searched)"
    )


class SlotSuggestion(BaseModel):
    """A single ranked slot suggestion."""

    start_time: datetime
    end_time: datetime
    travel_time_minutes: float = Field(
        ..., description="Estimated travel time from artisan's prior location"
    )
    travel_km: float = Field(
        ..., description="Estimated travel distance in km from artisan's prior location"
    )
    score: float = Field(
        ..., description="Scheduling score – higher is better (less travel waste)"
    )
    prior_job_location: str | None = Field(
        None, description="Description of where the artisan is coming from"
    )


class SlotSuggestionResponse(BaseModel):
    """Response containing ranked slot suggestions."""

    artisan_id: int
    preferred_date: datetime
    suggestions: list[SlotSuggestion]
