"""InventoryNotification ORM model.

Requirements: 4.4
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.sql import func

from app.db.base import Base


class InventoryNotification(Base):
    __tablename__ = "inventory_notifications"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    # No FK to jobs.id — jobs table has no ORM model in this project
    job_id = Column(Uuid, nullable=False)
    artisan_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    bom_item_id = Column(Uuid, nullable=False)
    store_id = Column(Uuid, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    # delivery_status: sent, failed, retried
    delivery_status = Column(String(50), nullable=True)
    pre_pay_url = Column(Text, nullable=False)

    __table_args__ = (
        # Enforce one notification per BOM item per job (Requirement 4.4)
        UniqueConstraint("job_id", "bom_item_id", name="uq_inventory_notifications_job_bom_item"),
    )
