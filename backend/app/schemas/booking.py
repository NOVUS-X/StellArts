from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    estimated_cost: float | None = Field(
        None,
        gt=0,
        description="Optional client-provided estimate; the server calculates the range",
    )
    estimated_hours: float | None = Field(
        None, gt=0, description="Estimated hours for the job"
    )
    location: str | None = Field(
        None, max_length=500, description="Location for the service"
    )
    notes: str | None = Field(None, description="Additional notes")


class JobEstimateResponse(BaseModel):
    specialties: list[str]
    estimated_hours: float
    range_min: float
    range_max: float
    estimated_cost: float
    confidence: float


class BookingStatusUpdate(BaseModel):
    """Schema for updating booking status"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "confirmed", "required_materials": ["copper pipe"]}
        }
    )

    status: str = Field(..., description="New status for the booking")
    required_materials: list[str] | None = Field(
        None, description="Optional list of required materials for the job"
    )


class ClientSuppliesOverrideRequest(BaseModel):
    """Schema for client to indicate they have the supplies"""

    client_supplies_override: bool = Field(
        True, description="True if client has supplies"
    )


class BidCreate(BaseModel):
    """Schema for artisan to submit a counter-offer/bid"""

    bid_amount: float = Field(..., gt=0, description="The counter-offer amount")
    justification: str | None = Field(
        None, description="Justification required if bid > 300% of range"
    )


class BookingCompletionVerificationRequest(BaseModel):
    """Schema for job-completion verification input."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scope_hash": "scopehash_abc123",
                "sow": "Replace the front porch steps with stone and finish the landing.",
                "after_photos": [
                    "https://cdn.example.com/jobs/booking-123-after-1.jpg",
                    "https://cdn.example.com/jobs/booking-123-after-2.jpg",
                ],
            }
        }
    )

    scope_hash: str | None = Field(
        None, max_length=128, description="ScopeHash for the original SOW"
    )
    sow: str | None = Field(
        None, min_length=1, description="Scope of work used by the verifier"
    )
    after_photos: list[str] = Field(
        default_factory=list,
        min_length=1,
        description="Final photos or image URLs from the artisan",
    )


class BookingCompletionVerificationResponse(BaseModel):
    """Schema for job-completion verification output."""

    booking_id: UUID
    status: str
    completion_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for completion"
    )
    verified: bool
    scope_hash: str | None = None
    summary: str
    matched_deliverables: list[str] = Field(default_factory=list)
    missing_deliverables: list[str] = Field(default_factory=list)
    fundamentally_wrong: list[str] = Field(default_factory=list)


class BookingResponse(BaseModel):
    """Schema for booking response"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: int
    artisan_id: int
    service: str
    job_specialties: list[str] = Field(default_factory=list)
    date: datetime | None
    estimated_cost: float | None
    estimated_hours: float | None
    labor_cost: float | None
    material_cost: float | None
    range_min: float | None
    range_max: float | None
    artisan_pitch: str | None
    status: str
    location: str | None
    notes: str | None
    client_supplies_override: bool = False
    created_at: datetime
    updated_at: datetime | None

    @field_validator("job_specialties", mode="before")
    @classmethod
    def parse_job_specialties(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [item.strip() for item in value.split(",") if item.strip()]
        return value or []


class ProposeSlotsRequest(BaseModel):
    """Schema for requesting proposed time slots"""

    artisan_id: int = Field(..., description="ID of the artisan to book")
    location: str = Field(..., description="Location of the job")
    estimated_hours: float = Field(..., gt=0, description="Estimated hours for the job")
    target_date: datetime = Field(..., description="Target date for the job")


class ProposedSlotResponse(BaseModel):
    """Schema for a proposed time slot"""

    start_time: datetime
    end_time: datetime
    transit_time_from_preceding_mins: float
    total_transit_waste_mins: float


class ReviewCreate(BaseModel):
    """Schema for creating a new review"""

    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: str | None = Field(None, description="Optional text comment")


class ReviewResponse(BaseModel):
    """Schema for review response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: UUID
    client_id: int
    artisan_id: int
    rating: int
    comment: str | None
    created_at: datetime
