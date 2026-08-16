from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MessageBase(BaseModel):
    content: str


class MessageCreate(MessageBase):
    receiver_id: int


class MessageOut(MessageBase):
    id: int
    sender_id: int
    receiver_id: int
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationOut(BaseModel):
    other_user_id: int
    other_user_name: str | None = None
    other_user_avatar: str | None = None
    last_message: MessageOut
    unread_count: int


class WebSocketEvent(BaseModel):
    type: str
    data: dict
