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


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    HELD = "held"
    RELEASED = "released"
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
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    booking = relationship("Booking", backref="payments")


class PaymentAuditEventType(enum.Enum):
    """Types of payment lifecycle events for audit logging."""

    PAYMENT_PREPARED = "payment_prepared"
    PAYMENT_SUBMITTED = "payment_submitted"
    PAYMENT_HELD = "payment_held"
    PAYMENT_RELEASED = "payment_released"
    PAYMENT_REFUNDED = "payment_refunded"
    PAYMENT_FAILED = "payment_failed"


class PaymentAudit(Base):
    """Immutable audit log for all payment lifecycle events.

    Once written, records should never be modified or deleted to maintain
    a clear audit trail for financial transactions.
    """

    __tablename__ = "payment_audits"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    payment_id = Column(Uuid, ForeignKey("payments.id"), nullable=True)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)

    # Event details
    event_type = Column(Enum(PaymentAuditEventType), nullable=False)
    old_status = Column(Enum(PaymentStatus), nullable=True)
    new_status = Column(Enum(PaymentStatus), nullable=True)

    # Transaction details
    transaction_hash = Column(String, nullable=True)
    amount = Column(Numeric(18, 7), nullable=True)
    from_account = Column(String(56), nullable=True)
    to_account = Column(String(56), nullable=True)
    memo = Column(String, nullable=True)

    # Additional context
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(String(500), nullable=True)

    # Metadata
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    payment = relationship("Payment", backref="audits")
    booking = relationship("Booking", backref="payment_audits")
