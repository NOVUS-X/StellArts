from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class NotificationBase(BaseModel):
    type: str
    title: str
    message: str
    reference_id: Optional[UUID] = None


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationUpdate(BaseModel):
    is_read: bool


class NotificationOut(NotificationBase):
    id: UUID
    user_id: int
    read: bool = Field(alias="is_read")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class UnreadCountOut(BaseModel):
    unread_count: int


class MarkAllAsReadOut(BaseModel):
    message: str


class NotificationDeleteOut(BaseModel):
    message: str
