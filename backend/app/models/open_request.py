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


class OpenRequestStatus(enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class OpenRequest(Base):
    __tablename__ = "open_requests"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    budget = Column(DECIMAL(10, 2), nullable=True)
    location_lat = Column(DECIMAL(10, 8), nullable=True)
    location_lng = Column(DECIMAL(11, 8), nullable=True)
    status = Column(Enum(OpenRequestStatus), default=OpenRequestStatus.OPEN)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("Client", backref="open_requests")
