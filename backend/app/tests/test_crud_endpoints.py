import csv
import io
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .conftest import TestingSessionLocal


def get_auth_headers(client, email, password, role):
    # Register
    client.post(
        "api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": f"Test {role.capitalize()}",
            "phone": "9999999999",
        },
    )
    # Login
    login_resp = client.post(
        "api/v1/auth/login", json={"email": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_booking_flow(client):
    # 1. Create Artisan
    artisan_headers = get_auth_headers(client, "art@test.com", "Pass123!", "artisan")

    # Create profile
    artisan_profile = {
        "business_name": "Artisan Services",
        "description": "Best services",
        "hourly_rate": 50.0,
        "specialties": ["plumbing"],
    }
    resp = client.post(
        "api/v1/artisans/profile", json=artisan_profile, headers=artisan_headers
    )
    assert resp.status_code == 200
    artisan_id = resp.json()["id"]

    # 2. Create Client and Booking
    client_headers = get_auth_headers(client, "cli@test.com", "Pass123!", "client")

    booking_data = {
        "artisan_id": artisan_id,
        "service": "Fix my sink",
        "estimated_hours": 2,
        "estimated_cost": 100.0,
        "date": "2024-12-25T10:00:00",
        "location": "123 Main St",
        "notes": "Urgent",
    }
    resp = client.post(
        "api/v1/bookings/create", json=booking_data, headers=client_headers
    )
    assert resp.status_code == 201
    booking_id = resp.json()["id"]

    # 3. Verify Client Bookings
    resp = client.get("api/v1/bookings/my-bookings", headers=client_headers)
    assert resp.status_code == 200
    bookings = resp.json()
    assert len(bookings) == 1
    assert bookings[0]["id"] == booking_id

    # 4. Verify Artisan Bookings
    resp = client.get("api/v1/artisans/my-bookings", headers=artisan_headers)
    assert resp.status_code == 200
    bookings = resp.json()
    assert len(bookings) == 3

    # 5. Artisan accepts booking
    status_update = {"status": "confirmed"}
    resp = client.put(
        f"api/v1/bookings/{booking_id}/status",
        json=status_update,
        headers=artisan_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    # 6. Verify status change
    resp = client.get("api/v1/bookings/my-bookings", headers=client_headers)
    assert resp.json()[0]["status"] == "confirmed"


def test_artisan_profile_crud(client):
    headers = get_auth_headers(client, "art2@test.com", "Pass123!", "artisan")

    # Create
    profile_data = {"business_name": "New Biz", "specialties": ["painting"]}
    resp = client.post("api/v1/artisans/profile", json=profile_data, headers=headers)
    assert resp.status_code == 200
    art_id = resp.json()["id"]

    # Get Public Profile
    resp = client.get(f"api/v1/artisans/{art_id}/profile")
    assert resp.status_code == 200
    # The new response structure is flat (not wrapped in "profile") and "specialty" is processed
    assert resp.json()["specialty"] == "painting"  # First item in list


def test_artisan_availability_update_online_offline_and_last_active(client):
    headers = get_auth_headers(client, "available@test.com", "Pass123!", "artisan")
    profile_data = {
        "business_name": "Availability Biz",
        "specialties": ["painting"],
        "latitude": 40.0,
        "longitude": -74.0,
    }
    resp = client.post("api/v1/artisans/profile", json=profile_data, headers=headers)
    assert resp.status_code == 200

    offline_resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert offline_resp.status_code == 200
    offline_data = offline_resp.json()
    assert offline_data["is_available"] is False
    assert offline_data["last_active"] is not None
    offline_last_active = datetime.fromisoformat(
        offline_data["last_active"].replace("Z", "+00:00")
    )

    online_resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": True},
        headers=headers,
    )
    assert online_resp.status_code == 200
    online_data = online_resp.json()
    assert online_data["is_available"] is True
    online_last_active = datetime.fromisoformat(
        online_data["last_active"].replace("Z", "+00:00")
    )
    assert online_last_active >= offline_last_active


def test_artisan_availability_requires_authentication(client):
    resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": False},
    )
    assert resp.status_code in (401, 403)


def test_artisan_availability_rejects_non_artisan(client):
    headers = get_auth_headers(client, "not-artisan@test.com", "Pass123!", "client")

    resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert resp.status_code == 403


def test_artisan_can_export_completed_jobs_as_csv(client):
    from app.models.artisan import Artisan
    from app.models.booking import Booking, BookingStatus
    from app.models.payment import Payment, PaymentStatus
    from app.models.review import Review

    artisan_headers = get_auth_headers(
        client, "export-art@test.com", "Pass123!", "artisan"
    )
    artisan_profile = {
        "business_name": "Export Biz",
        "description": "Export-ready services",
        "hourly_rate": 75.0,
        "specialties": ["painting"],
    }
    profile_resp = client.post(
        "api/v1/artisans/profile", json=artisan_profile, headers=artisan_headers
    )
    assert profile_resp.status_code == 200

    client_headers = get_auth_headers(
        client, "export-cli@test.com", "Pass123!", "client"
    )

    completed_booking_resp = client.post(
        "api/v1/bookings/create",
        json={
            "artisan_id": profile_resp.json()["id"],
            "service": "Wall painting",
            "estimated_hours": 3,
            "estimated_cost": 225.0,
            "date": "2025-01-15T10:00:00",
            "location": "12 Main St",
            "notes": "Use matte finish",
        },
        headers=client_headers,
    )
    assert completed_booking_resp.status_code == 201
    completed_booking_id = UUID(completed_booking_resp.json()["id"])

    pending_booking_resp = client.post(
        "api/v1/bookings/create",
        json={
            "artisan_id": profile_resp.json()["id"],
            "service": "Ceiling repair",
            "estimated_hours": 2,
            "estimated_cost": 180.0,
            "date": "2025-01-16T09:00:00",
            "location": "14 Main St",
            "notes": "Pending job",
        },
        headers=client_headers,
    )
    assert pending_booking_resp.status_code == 201

    db = TestingSessionLocal()
    try:
        artisan = (
            db.query(Artisan).filter(Artisan.id == profile_resp.json()["id"]).first()
        )
        completed_booking = (
            db.query(Booking).filter(Booking.id == completed_booking_id).first()
        )
        assert artisan is not None
        assert completed_booking is not None
        client_id = completed_booking.client_id

        completed_booking.status = BookingStatus.COMPLETED
        db.add(
            Payment(
                booking_id=completed_booking.id,
                amount=Decimal("225.00"),
                status=PaymentStatus.RELEASED,
            )
        )
        db.add(
            Review(
                booking_id=completed_booking.id,
                client_id=completed_booking.client_id,
                artisan_id=artisan.id,
                rating=5,
                comment="Excellent work",
            )
        )
        db.commit()
    finally:
        db.close()

    export_resp = client.get("api/v1/artisans/me/export", headers=artisan_headers)

    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("text/csv")
    assert "attachment;" in export_resp.headers["content-disposition"]
    assert ".csv" in export_resp.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(export_resp.text)))
    assert len(rows) == 1
    assert rows[0] == {
        "Date": "2025-01-15",
        "Job Title": "Wall painting",
        "Client ID": str(client_id),
        "Amount Earned": "225.00",
        "Rating": "5",
    }
