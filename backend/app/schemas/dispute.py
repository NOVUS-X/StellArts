from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DisputeResolve(BaseModel):
    """Schema for resolving a dispute"""

    payout_artisan_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Ratio of funds to release to artisan (0.0 to 1.0)"
    )
    resolution_memo: str = Field(..., min_length=1, description="Reasoning for the resolution")


class DisputeResponse(BaseModel):
    """Schema for dispute response"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    booking_id: UUID
    payment_id: UUID
    reason: str
    status: str
    payout_artisan_ratio: float | None = None
    resolution_memo: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    created_at: datetime
    updated_at: datetime
