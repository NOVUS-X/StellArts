from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookingCreate(BaseModel):
    """Schema for creating a new booking"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "artisan_id": 1,
                "service": "Plumbing repair for kitchen sink",
                "date": "2026-02-15T10:00:00",
                "estimated_cost": 150.00,
                "estimated_hours": 2.5,
                "location": "123 Main St, Apt 4B",
                "notes": "Please bring replacement parts",
            }
        }
    )

    artisan_id: int = Field(..., description="ID of the artisan to book")
    service: str = Field(..., min_length=1, description="Description of the service")
    date: datetime = Field(..., description="Scheduled date and time for the service")
    estimated_cost: float = Field(
        ..., gt=0, description="Estimated cost of the service"
    )
    estimated_hours: float | None = Field(
        None, gt=0, description="Estimated hours for the job"
    )
    location: str | None = Field(
        None, max_length=500, description="Location for the service"
    )
    notes: str | None = Field(None, description="Additional notes")


class BookingStatusUpdate(BaseModel):
    """Schema for updating booking status"""

    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "confirmed"}}
    )

    status: str = Field(..., description="New status for the booking")


class BookingResponse(BaseModel):
    """Schema for booking response"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: int
    artisan_id: int
    service: str
    date: datetime | None
    estimated_cost: float | None
    estimated_hours: float | None
    status: str
    location: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
