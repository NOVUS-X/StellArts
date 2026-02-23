import time
from unittest.mock import patch

import pytest

from app.core.email_verification import generate_verification_token
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.models.artisan import Artisan
from app.core.config import settings


def make_register_payload(email: str = "test@example.com"):
    return {
        "email": email,
        "password": "Password1!",
        "role": "client",
        "full_name": "Test User",
    }


def test_register_sends_verification_email(client):
    payload = make_register_payload("regtest@example.com")
    with patch("app.api.v1.endpoints.auth.send_verification_email") as mock_send:
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        # Background task should have scheduled the send
        assert mock_send.call_count == 1


def test_verify_email_with_valid_token(client, db_session):
    # Create an unverified user in DB
    hashed = get_password_hash("Password1!")
    user = User(email="vt@example.com", hashed_password=hashed, role="client")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = generate_verification_token(user.id, user.email)
    resp = client.get(f"/api/v1/auth/verify-email?token={token}&email={user.email}")
    assert resp.status_code == 200
    # Refresh the local session state so we observe commits from the app
    db_session.refresh(user)
    assert user.is_verified is True


def test_verify_email_with_expired_token(client, db_session, monkeypatch):
    # Token generated at epoch (0) will be expired
    hashed = get_password_hash("Password1!")
    user = User(email="exp@example.com", hashed_password=hashed, role="client")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create token with timestamp 0
    original_time = time.time
    monkeypatch.setattr(time, "time", lambda: 0)
    token = generate_verification_token(user.id, user.email)
    # Restore time to current so verification fails due to expiry
    monkeypatch.setattr(time, "time", original_time)

    resp = client.get(f"/api/v1/auth/verify-email?token={token}&email={user.email}")
    assert resp.status_code == 400


def test_unverified_user_cannot_book(client, db_session):
    # Enable enforcement for this test and restore after
    original = settings.REQUIRE_EMAIL_VERIFICATION
    settings.REQUIRE_EMAIL_VERIFICATION = True
    try:
        # Create a client user (unverified)
        hashed = get_password_hash("Password1!")
        client_user = User(email="unv@example.com", hashed_password=hashed, role="client")
        db_session.add(client_user)
        db_session.commit()
        db_session.refresh(client_user)

        # Create an artisan to book
        artisan_user = User(email="art@example.com", hashed_password=hashed, role="artisan", is_verified=True)
        db_session.add(artisan_user)
        db_session.commit()
        db_session.refresh(artisan_user)

        artisan = Artisan(user_id=artisan_user.id, business_name="Art Corp")
        db_session.add(artisan)
        db_session.commit()
        db_session.refresh(artisan)

        token = create_access_token(subject=client_user.id)

        booking_payload = {
            "artisan_id": artisan.id,
            "service": "Test Service",
            "date": "2026-02-15T10:00:00",
            "estimated_cost": 100.0,
        }

        resp = client.post(
            "/api/v1/bookings/create",
            json=booking_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
    finally:
        settings.REQUIRE_EMAIL_VERIFICATION = original


def test_verified_user_can_book(client, db_session):
    # Create a verified client user
    hashed = get_password_hash("Password1!")
    client_user = User(email="vclient@example.com", hashed_password=hashed, role="client", is_verified=True)
    db_session.add(client_user)
    db_session.commit()
    db_session.refresh(client_user)

    # Create artisan to book
    artisan_user = User(email="art2@example.com", hashed_password=hashed, role="artisan", is_verified=True)
    db_session.add(artisan_user)
    db_session.commit()
    db_session.refresh(artisan_user)

    artisan = Artisan(user_id=artisan_user.id, business_name="Artistry")
    db_session.add(artisan)
    db_session.commit()
    db_session.refresh(artisan)

    token = create_access_token(subject=client_user.id)

    booking_payload = {
        "artisan_id": artisan.id,
        "service": "Real Service",
        "date": "2026-02-16T11:00:00",
        "estimated_cost": 200.0,
    }

    resp = client.post(
        "/api/v1/bookings/create",
        json=booking_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


def test_resend_verification_fails_if_already_verified(client, db_session):
    hashed = get_password_hash("Password1!")
    user = User(email="resend@example.com", hashed_password=hashed, role="client", is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(subject=user.id)

    resp = client.post(
        "/api/v1/auth/resend-verification",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
