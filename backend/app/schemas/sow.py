from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


class SOWCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "booking_id": "00000000-0000-0000-0000-000000000000",
                "issue12_output": "Parsed job summary from Issue-12",
                "user_voice_intent": "I want it finished by next Friday and make sure they know the gate is locked",
            }
        }
    )

    booking_id: UUID
    issue12_output: str
    user_voice_intent: str


class SOWResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    booking_id: UUID
    content: str
    status: str
    version: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime | None


class SOWFeedback(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"feedback": "Make sure they know the gate is locked"}
        }
    )

    feedback: str


class SOWApprove(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"approved_by": 1}})

    approved_by: int
