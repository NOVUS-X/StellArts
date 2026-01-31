from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

from app.models.user import User
from app.models.artisan import Artisan
from app.models.client import Client
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.review import Review
from app.models.portfolio import Portfolio
