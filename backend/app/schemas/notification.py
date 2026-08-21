from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationBase(BaseModel):
    type: str = Field(..., max_length=50)
    title: str = Field(..., max_length=255)
    message: str
    reference_id: str | None = None


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationOut(NotificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: int
    is_read: bool
    read: bool = False
    created_at: datetime
    updated_at: datetime

    def __init__(self, **data):
        if "is_read" in data and "read" not in data:
            data["read"] = data["is_read"]
        super().__init__(**data)


class UnreadCountResponse(BaseModel):
    unread_count: int
