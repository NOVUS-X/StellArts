from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    """Schema for creating a new review"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "booking_id": "550e8400-e29b-41d4-a716-446655440000",
                "artisan_id": 1,
                "rating": 5,
                "comment": "Excellent work! Very professional and completed the job on time.",
            }
        }
    )

    booking_id: UUID = Field(..., description="ID of the completed booking")
    artisan_id: int = Field(..., description="ID of the artisan being reviewed")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: str | None = Field(
        None, max_length=500, description="Optional detailed feedback"
    )


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
