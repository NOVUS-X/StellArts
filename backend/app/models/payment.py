import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    amount = Column(Numeric(18, 7), nullable=False)

     # Stellar fields
    from_account = Column(String(56), nullable=True)
    to_account = Column(String(56), nullable=True)
    memo = Column(String, nullable=True)
    transaction_hash = Column(String, unique=True, index=True, nullable=True)

    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at = Column( DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column( DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    booking = relationship("Booking", backref="payments")
