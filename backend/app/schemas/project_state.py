from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.ingestion import StoredMedia


class StrictBaseModel(BaseModel):
    model_config = {"extra": "forbid"}


class ExtractedMaterial(StrictBaseModel):
    name: str = Field(min_length=1)
    quantity: str | None = None
    notes: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class StructuralDamage(StrictBaseModel):
    type: str = Field(min_length=1)
    location: str | None = None
    severity: Literal["low", "moderate", "high", "critical"]
    notes: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ScopeConstraints(StrictBaseModel):
    area_sq_ft: float | None = Field(default=None, ge=0)
    dimensions: str | None = None
    access_constraints: list[str] = Field(default_factory=list)
    safety_constraints: list[str] = Field(default_factory=list)
    additional_notes: list[str] = Field(default_factory=list)


class ProjectState(StrictBaseModel):
    job_id: str
    session_id: str | None = None
    client_reference: str | None = None
    status: Literal["scoped"]
    summary: str = Field(min_length=1)
    required_materials: list[ExtractedMaterial] = Field(default_factory=list)
    structural_damage: list[StructuralDamage] = Field(default_factory=list)
    scope_constraints: ScopeConstraints
    source_media: list[StoredMedia] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_name: str


class VisionAnalysisJob(StrictBaseModel):
    job_id: str
    session_id: str | None = None
    client_reference: str | None = None
    created_at: datetime
    media: list[StoredMedia] = Field(default_factory=list)
    status: Literal["queued_for_analysis", "validated", "executed"]
    transcript: str | None = None
    site_notes: str | None = None


class VisionExecutionRequest(StrictBaseModel):
    payload: VisionAnalysisJob


class VisionExecutionMetadata(StrictBaseModel):
    model_name: str
    media_parts_sent: int
    prompt_preview: str
    raw_response: dict[str, Any]

