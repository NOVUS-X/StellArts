from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Import all models here to register them with Base.metadata
from app.models.artisan import Artisan  # noqa: F401, E402
from app.models.booking import Booking  # noqa: F401, E402
from app.models.client import Client  # noqa: F401, E402
from app.models.payment import Payment  # noqa: F401, E402
from app.models.portfolio import Portfolio  # noqa: F401, E402
from app.models.review import Review  # noqa: F401, E402
from app.models.user import User  # noqa: F401, E402
