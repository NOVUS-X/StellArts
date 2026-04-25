import enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class DisputeStatus(enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    payment_id = Column(Uuid, ForeignKey("payments.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(DisputeStatus), default=DisputeStatus.OPEN)

    # Resolution details
    payout_artisan_ratio = Column(Numeric(3, 2), nullable=True)  # e.g., 0.70 for 70% to artisan
    resolution_memo = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String, nullable=True)  # Admin username or ID

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    booking = relationship("Booking", backref="disputes")
    payment = relationship("Payment", backref="disputes")
