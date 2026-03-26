from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ValidationFeedback(BaseModel):
    code: str
    message: str
    media_type: Literal["photo", "video", "voice"]
    filename: str | None = None


class StoredMedia(BaseModel):
    media_type: Literal["photo", "video", "voice"]
    filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    metadata: dict[str, float | int | str | bool | None] = Field(default_factory=dict)


class VisionToScopeResponse(BaseModel):
    job_id: str
    session_id: str | None = None
    status: Literal["accepted", "rejected"]
    forwarded_to_queue: bool
    queue_name: str
    feedback: list[ValidationFeedback] = Field(default_factory=list)
    stored_media: list[StoredMedia] = Field(default_factory=list)
    created_at: datetime
