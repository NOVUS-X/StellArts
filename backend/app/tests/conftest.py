import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    """Create a test client."""
    from unittest.mock import AsyncMock, patch

    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)

    # Mock Redis cache (Async) and Security Redis (Sync) to avoid connection errors
    with (
        patch("app.core.cache.cache.initialize", new_callable=AsyncMock),
        patch("app.core.cache.cache.redis", new_callable=AsyncMock),
        patch("app.core.security.redis_client"),
    ):
        with TestClient(app) as test_client:
            yield test_client

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()
