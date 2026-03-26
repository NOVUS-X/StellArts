from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.sql import func

from app.db.base import Base


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id = Column(Integer, primary_key=True)
    artisan_id = Column(Integer, ForeignKey("artisans.id"), nullable=False)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    store_id = Column(String(100), nullable=False)
    item_sku = Column(String(100), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    fcm_success = Column(Boolean, nullable=False)
