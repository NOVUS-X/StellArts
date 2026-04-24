from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PaymentAuditBase(BaseModel):
    event_type: str
    old_status: str | None = None
    new_status: str | None = None
    transaction_hash: str | None = None
    amount: Decimal | None = None
    from_account: str | None = None
    to_account: str | None = None
    memo: str | None = None
    description: str | None = None


class PaymentAuditResponse(PaymentAuditBase):
    id: UUID
    payment_id: UUID | None = None
    booking_id: UUID
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentAuditListResponse(BaseModel):
    """Response for listing payment audits."""

    audits: list[PaymentAuditResponse]
    total: int
