# Import database components
from app.db.base import Base

# Import models so Alembic/Base.metadata discovers them
from app.models import calendar as _calendar_models  # noqa: F401

# Re-export for convenience
__all__ = ["Base"]
