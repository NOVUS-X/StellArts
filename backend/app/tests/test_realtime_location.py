"""Tests for the Redis-only real-time artisan location endpoint.

PUT /api/v1/artisans/location/realtime
- Secured with require_artisan (artisan role only).
- Must NOT write to PostgreSQL.
- Returns {"status": "ok"} on success.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Ensure required env vars are set before importing app modules.
os.environ.setdefault("SECRET_KEY", "test-secret-key-realtime")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_realtime.db")
os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "False")

from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings as _settings
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User

_settings.REQUIRE_EMAIL_VERIFICATION = False

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_realtime.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

REALTIME_LOCATION_URL = "/api/v1/artisans/location/realtime"
VALID_PAYLOAD = {"latitude": 6.5244, "longitude": 3.3792}


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Create schema once per test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def test_client():
    """TestClient with DB and Redis mocked out."""
    app.dependency_overrides[get_db] = override_get_db
    with (
        patch("app.core.cache.cache.initialize", new_callable=AsyncMock),
        patch("app.core.cache.cache.redis", new_callable=AsyncMock),
        patch("app.core.security.redis_client"),
    ):
        with TestClient(app) as client:
            yield client
    app.dependency_overrides.clear()


def _create_user(role: str) -> User:
    """Insert a test user with the given role into the test DB."""
    db = TestingSessionLocal()
    try:
        user = User(
            email=f"{role}_realtime@test.com",
            hashed_password=get_password_hash("TestPass123!"),
            role=role,
            full_name=f"Test {role.capitalize()}",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _auth_headers(user_id: int) -> dict:
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Core test: non-artisan (client role) must be rejected
# ---------------------------------------------------------------------------


def test_client_role_cannot_update_realtime_location(test_client: TestClient):
    """A user with the 'client' role must receive 401 or 403 from the
    Redis-only real-time location endpoint — it is artisan-only."""
    client_user = _create_user("client")
    headers = _auth_headers(client_user.id)

    response = test_client.put(REALTIME_LOCATION_URL, json=VALID_PAYLOAD, headers=headers)

    assert response.status_code in (401, 403), (
        f"Expected 401 or 403 for client role, got {response.status_code}: "
        f"{response.json()}"
    )


def test_unauthenticated_request_is_rejected(test_client: TestClient):
    """Requests without any token must be rejected (401/403)."""
    response = test_client.put(REALTIME_LOCATION_URL, json=VALID_PAYLOAD)
    assert response.status_code in (401, 403), (
        f"Expected 401 or 403 for unauthenticated request, got {response.status_code}"
    )


def test_invalid_token_is_rejected(test_client: TestClient):
    """A syntactically invalid JWT must be rejected with 401."""
    headers = {"Authorization": "Bearer this.is.not.a.valid.token"}
    response = test_client.put(REALTIME_LOCATION_URL, json=VALID_PAYLOAD, headers=headers)
    assert response.status_code == 401, (
        f"Expected 401 for invalid token, got {response.status_code}"
    )
