"""InventoryCheckRun ORM model.

Requirements: 5.3
"""

import uuid

from sqlalchemy import Column, DateTime, Integer, JSON, String, Uuid
from sqlalchemy.sql import func

from app.db.base import Base


class InventoryCheckRun(Base):
    __tablename__ = "inventory_check_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    # No FK to jobs.id — jobs table has no ORM model in this project
    job_id = Column(Uuid, nullable=False)
    route_polyline = Column(JSON, nullable=False)
    corridor_meters = Column(Integer, nullable=False, default=500)
    # status: pending, completed, failed
    status = Column(String(50), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    result_summary = Column(JSON, nullable=True)
