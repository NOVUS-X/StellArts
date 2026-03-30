from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class UrgencyLevel(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"


class LaborPricingSuggestRequest(BaseModel):
    sow_text: str = Field(..., min_length=8, max_length=8000)
    zip_code: str = Field(..., min_length=5, max_length=10)
    urgency: UrgencyLevel = UrgencyLevel.normal
    artisan_average_rating: float | None = Field(
        default=None,
        ge=1.0,
        le=5.0,
        description="Optional 1–5 rating used to nudge the suggested labor price.",
    )


class MatchedLaborJob(BaseModel):
    anon_job_id: str
    similarity: float
    reference_labor_cost: float


class LaborPricingSuggestResponse(BaseModel):
    zip_code: str
    region_scope: str
    matches_used: int
    baseline_average_labor: float | None
    urgency_multiplier: float
    rating_multiplier: float
    suggested_labor_price: float | None
    matched_jobs: list[MatchedLaborJob]


class LaborPricingReindexResponse(BaseModel):
    indexed_jobs: int
    unique_zips: int
