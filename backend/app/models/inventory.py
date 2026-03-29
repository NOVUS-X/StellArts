from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.sql import func

from app.db.base import Base


class InventoryCheckResult(Base):
    __tablename__ = "inventory_check_results"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    bom_item_id = Column(Integer, ForeignKey("bom_items.id"), nullable=False)
    store_id = Column(String(100), nullable=False)
    store_name = Column(String(300), nullable=False)
    store_address = Column(String(500))
    available = Column(Boolean, nullable=False)
    pre_pay_url = Column(String(2048))
    status = Column(String(20), default="fresh")
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
