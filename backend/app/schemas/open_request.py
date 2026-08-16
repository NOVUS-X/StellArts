from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OpenRequestCreate(BaseModel):
    """Schema for creating a new open request"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Fix kitchen sink",
                "description": "Need a plumber to fix a leaking kitchen sink",
                "budget": 150.00,
                "location_lat": 40.7128,
                "location_lng": -74.0060,
            }
        }
    )

    title: str = Field(
        ..., min_length=1, max_length=255, description="Title of the request"
    )
    description: str | None = Field(None, description="Detailed description of the job")
    budget: float | None = Field(None, gt=0, description="Budget for the job")
    location_lat: float | None = Field(
        None, ge=-90, le=90, description="Latitude of the job location"
    )
    location_lng: float | None = Field(
        None, ge=-180, le=180, description="Longitude of the job location"
    )


class OpenRequestUpdate(BaseModel):
    """Schema for updating an open request"""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    budget: float | None = Field(None, gt=0)
    location_lat: float | None = Field(None, ge=-90, le=90)
    location_lng: float | None = Field(None, ge=-180, le=180)
    status: str | None = Field(
        None, description="Status: open, assigned, closed, cancelled"
    )


class OpenRequestResponse(BaseModel):
    """Schema for open request response"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: int
    title: str
    description: str | None
    budget: float | None
    location_lat: float | None
    location_lng: float | None
    status: str
    created_at: datetime
    updated_at: datetime | None


class OpenRequestListResponse(BaseModel):
    """Schema for list of open requests"""

    items: list[OpenRequestResponse]
    total: int
