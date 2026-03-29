import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class SOWStatus:
    DRAFT = "draft"
    FINALIZED = "finalized"


class SOW(Base):
    __tablename__ = "sows"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(50), default=SOWStatus.DRAFT)
    version = Column(Integer, default=1)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    booking = relationship("Booking", backref="sow_items")
