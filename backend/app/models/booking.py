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
    DISPUTED = "disputed"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    artisan_id = Column(Integer, ForeignKey("artisans.id"), nullable=False)
    service = Column(Text, nullable=False)
    estimated_hours = Column(DECIMAL(5, 2))
    estimated_cost = Column(DECIMAL(10, 2))
    labor_cost = Column(DECIMAL(10, 2))
    material_cost = Column(DECIMAL(10, 2))
    range_min = Column(DECIMAL(10, 2))
    range_max = Column(DECIMAL(10, 2))
    artisan_pitch = Column(Text)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    date = Column(DateTime(timezone=True))
    location = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("Client", backref="bookings")
    artisan = relationship("Artisan", backref="bookings")
