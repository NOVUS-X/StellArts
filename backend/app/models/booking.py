import enum
import uuid

from sqlalchemy import (
    DECIMAL,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class BookingStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    artisan_id = Column(Integer, ForeignKey("artisans.id"), nullable=False)
    service_description = Column(Text, nullable=False)
    estimated_hours = Column(DECIMAL(5, 2))
    estimated_cost = Column(DECIMAL(10, 2))
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    scheduled_date = Column(DateTime(timezone=True))
    location = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("Client", backref="bookings")
    artisan = relationship("Artisan", backref="bookings")
