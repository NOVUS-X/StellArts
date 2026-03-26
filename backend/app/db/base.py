from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Support SQLite for testing
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Import all models here so they are registered with Base.metadata
# (used by Alembic autogenerate and app startup)
def _register_models():
    from app.models import user, artisan, client, booking, payment, review, portfolio  # noqa: F401
    from app.models import bom, inventory, notification  # noqa: F401

_register_models()
