from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PaymentAuditBase(BaseModel):
    event_type: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    transaction_hash: Optional[str] = None
    amount: Optional[Decimal] = None
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    memo: Optional[str] = None
    description: Optional[str] = None


class PaymentAuditResponse(PaymentAuditBase):
    id: UUID
    payment_id: Optional[UUID] = None
    booking_id: UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentAuditListResponse(BaseModel):
    """Response for listing payment audits."""

    audits: list[PaymentAuditResponse]
    total: int
