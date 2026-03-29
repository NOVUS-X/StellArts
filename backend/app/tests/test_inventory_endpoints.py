"""Unit tests for inventory API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.booking import Booking, BookingStatus
from app.models.client import Client
from app.models.inventory import InventoryCheckResult
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_auth_headers(client, email, password, role):
    client.post(
        "api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": f"Test {role.capitalize()}",
            "phone": "1234567890",
        },
    )
    login_resp = client.post(
        "api/v1/auth/login", json={"email": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_artisan_and_booking(client, db_session):
    """Register an artisan and a client, create a booking, return (booking_id, client_headers, artisan_headers)."""
    artisan_headers = get_auth_headers(client, "art_inv@test.com", "Pass123!", "artisan")
    client_headers = get_auth_headers(client, "cli_inv@test.com", "Pass123!", "client")

    # Create artisan profile
    resp = client.post(
        "api/v1/artisans/profile",
        json={
            "business_name": "Test Artisan",
            "description": "desc",
            "hourly_rate": 50.0,
            "specialties": ["plumbing"],
        },
        headers=artisan_headers,
    )
    artisan_id = resp.json()["id"]

    # Create booking
    resp = client.post(
        "api/v1/bookings/create",
        json={
            "artisan_id": artisan_id,
            "service": "Fix sink",
            "estimated_hours": 1,
            "estimated_cost": 50.0,
            "date": "2025-12-25T10:00:00",
        },
        headers=client_headers,
    )
    assert resp.status_code == 201
    booking_id = resp.json()["id"]

    return booking_id, client_headers, artisan_headers


# ---------------------------------------------------------------------------
# GET /inventory/{booking_id}/results
# ---------------------------------------------------------------------------

def test_get_inventory_results_empty_list(client, db_session):
    """Returns empty list when no inventory results exist for a booking."""
    booking_id, client_headers, _ = create_artisan_and_booking(client, db_session)

    resp = client.get(f"api/v1/inventory/{booking_id}/results", headers=client_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def _get_booking_uuid(db_session, booking_id_str: str):
    """Retrieve the actual Booking UUID object from the DB (handles SQLite UUID quirks)."""
    bookings = db_session.query(Booking).all()
    for b in bookings:
        if str(b.id) == booking_id_str:
            return b.id
    return uuid.UUID(booking_id_str)


def test_get_inventory_results_fresh(client, db_session):
    """Returns results with status='fresh' when checked_at is recent."""
    booking_id, client_headers, _ = create_artisan_and_booking(client, db_session)
    booking_uuid = _get_booking_uuid(db_session, booking_id)

    result = InventoryCheckResult(
        booking_id=booking_uuid,
        bom_item_id=1,
        store_id="store-1",
        store_name="Test Store",
        store_address="123 Main St",
        available=True,
        pre_pay_url="http://pay",
        status="fresh",
        checked_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(result)
    db_session.commit()

    resp = client.get(f"api/v1/inventory/{booking_id}/results", headers=client_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "fresh"
    assert data[0]["store_id"] == "store-1"


def test_get_inventory_results_marks_stale(client, db_session):
    """Results with checked_at older than 24h are returned with status='stale'."""
    booking_id, client_headers, _ = create_artisan_and_booking(client, db_session)
    booking_uuid = _get_booking_uuid(db_session, booking_id)

    result = InventoryCheckResult(
        booking_id=booking_uuid,
        bom_item_id=1,
        store_id="store-old",
        store_name="Old Store",
        store_address=None,
        available=True,
        pre_pay_url=None,
        status="fresh",
        checked_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    db_session.add(result)
    db_session.commit()

    resp = client.get(f"api/v1/inventory/{booking_id}/results", headers=client_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "stale"


def test_get_inventory_results_mixed_staleness(client, db_session):
    """Fresh and stale results are correctly differentiated."""
    booking_id, client_headers, _ = create_artisan_and_booking(client, db_session)
    booking_uuid = _get_booking_uuid(db_session, booking_id)

    fresh = InventoryCheckResult(
        booking_id=booking_uuid,
        bom_item_id=1,
        store_id="fresh-store",
        store_name="Fresh Store",
        store_address=None,
        available=True,
        pre_pay_url=None,
        status="fresh",
        checked_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    stale = InventoryCheckResult(
        booking_id=booking_uuid,
        bom_item_id=2,
        store_id="stale-store",
        store_name="Stale Store",
        store_address=None,
        available=False,
        pre_pay_url=None,
        status="fresh",
        checked_at=datetime.now(timezone.utc) - timedelta(hours=30),
    )
    db_session.add_all([fresh, stale])
    db_session.commit()

    resp = client.get(f"api/v1/inventory/{booking_id}/results", headers=client_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    by_store = {r["store_id"]: r["status"] for r in data}
    assert by_store["fresh-store"] == "fresh"
    assert by_store["stale-store"] == "stale"


# ---------------------------------------------------------------------------
# POST /bookings/{booking_id}/supply-override
# ---------------------------------------------------------------------------

def test_supply_override_returns_403_for_non_owner(client, db_session):
    """Returns 403 when the caller is not the booking owner."""
    booking_id, _, _ = create_artisan_and_booking(client, db_session)

    # Register a different client
    other_headers = get_auth_headers(client, "other_cli@test.com", "Pass123!", "client")

    resp = client.post(
        f"api/v1/bookings/{booking_id}/supply-override",
        json={"client_supply_override": True},
        headers=other_headers,
    )
    assert resp.status_code == 403


def test_supply_override_returns_403_for_wrong_status(client, db_session):
    """Returns 403 when booking status is not PENDING or CONFIRMED."""
    booking_id, client_headers, _ = create_artisan_and_booking(client, db_session)
    booking_uuid = _get_booking_uuid(db_session, booking_id)

    # Directly set status to COMPLETED in DB
    booking = db_session.query(Booking).filter(Booking.id == booking_uuid).first()
    booking.status = BookingStatus.COMPLETED
    db_session.commit()

    resp = client.post(
        f"api/v1/bookings/{booking_id}/supply-override",
        json={"client_supply_override": True},
        headers=client_headers,
    )
    assert resp.status_code == 403


def test_supply_override_succeeds_for_owner_pending(client, db_session):
    """Owner can set supply override on a PENDING booking."""
    booking_id, client_headers, _ = create_artisan_and_booking(client, db_session)

    resp = client.post(
        f"api/v1/bookings/{booking_id}/supply-override",
        json={"client_supply_override": True},
        headers=client_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_supply_override"] is True
    assert data["id"] == booking_id


def test_supply_override_succeeds_for_owner_confirmed(client, db_session):
    """Owner can set supply override on a CONFIRMED booking."""
    booking_id, client_headers, _ = create_artisan_and_booking(client, db_session)
    booking_uuid = _get_booking_uuid(db_session, booking_id)

    booking = db_session.query(Booking).filter(Booking.id == booking_uuid).first()
    booking.status = BookingStatus.CONFIRMED
    db_session.commit()

    resp = client.post(
        f"api/v1/bookings/{booking_id}/supply-override",
        json={"client_supply_override": False},
        headers=client_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["client_supply_override"] is False


def test_supply_override_requires_auth(client):
    """Unauthenticated request returns 401 or 403."""
    fake_id = str(uuid.uuid4())
    resp = client.post(
        f"api/v1/bookings/{fake_id}/supply-override",
        json={"client_supply_override": True},
    )
    assert resp.status_code in (401, 403)
