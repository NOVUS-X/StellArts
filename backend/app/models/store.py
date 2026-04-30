"""Store model — represents a physical supply store with geolocation."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, Float, String, Text, Uuid

from app.db.base import Base


class Store(Base):
    __tablename__ = "stores"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    # Lat/lon stored as plain floats — no PostGIS dependency required
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    # JSON array of {sku, name, quantity, unit_price} objects
    inventory_json = Column(Text, nullable=True)
    # Optional external store identifier (e.g. "HD-402")
    external_id = Column(String(64), nullable=True, index=True)
