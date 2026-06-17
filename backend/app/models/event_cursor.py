from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class EventCursor(Base):
    __tablename__ = "event_cursors"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(String(56), index=True, unique=True, nullable=False)
    last_cursor = Column(String, nullable=False, default="0")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
