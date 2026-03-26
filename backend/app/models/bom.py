from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.sql import func

from app.db.base import Base


class BOMItem(Base):
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    sku = Column(String(100), nullable=False)
    name = Column(String(300), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
