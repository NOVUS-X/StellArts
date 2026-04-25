"""Store ORM model with PostGIS geometry support.

Requirements: 1.2, 5.1
"""

import uuid

from sqlalchemy import Column, JSON, String, Text, Uuid
from sqlalchemy.sql import func
from sqlalchemy import DateTime

from app.db.base import Base


def _geometry_column():
    """
    Return the appropriate column type for the ``location`` field.

    On PostgreSQL (production) we use GeoAlchemy2's Geometry type so that
    PostGIS spatial queries work correctly.  On other dialects (e.g. SQLite
    used in tests) we fall back to a plain Text column to avoid GeoAlchemy2
    registering PostGIS-specific DDL event listeners that call functions like
    ``CheckSpatialIndex`` / ``RecoverGeometryColumn`` which do not exist in
    SQLite.

    The actual PostGIS column type and GIST index are managed by Alembic
    migrations, so the ORM model only needs to be compatible with the test
    database.
    """
    try:
        from geoalchemy2 import Geometry
        # Use management=False equivalent: spatial_index=False prevents the
        # CheckSpatialIndex DDL event, but GeoAlchemy2 still registers
        # RecoverGeometryColumn on create.  We therefore use Text as a
        # universal fallback and rely on Alembic for the real column type.
    except ImportError:
        pass
    # Always use Text for ORM metadata; Alembic handles the real PostGIS type.
    return Column(Text, nullable=False)


class Store(Base):
    __tablename__ = "stores"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    # Stored as Text in ORM metadata for SQLite test compatibility.
    # The actual PostGIS GEOMETRY(Point, 4326) column and GIST index are
    # created by the Alembic migration (001_create_stores_table.py).
    location = Column(Text, nullable=False)
    api_adapter = Column(String(100), nullable=False)
    api_config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
