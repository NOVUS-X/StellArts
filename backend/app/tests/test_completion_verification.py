from uuid import UUID

from app.models.booking import Booking


def get_auth_headers(client, email, password, role):
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
    login_resp = client.post(
        "api/v1/auth/login", json={"email": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_artisan_and_client(client):
    artisan_headers = get_auth_headers(
        client, "vision-artisan@test.com", "Pass123!", "artisan"
    )
    artisan_profile = {
        "business_name": "Vision Masonry",
        "description": "Stone and masonry restoration",
        "hourly_rate": 120.0,
        "specialties": ["stonework", "masonry"],
    }
    resp = client.post(
        "api/v1/artisans/profile", json=artisan_profile, headers=artisan_headers
    )
    assert resp.status_code == 200
    artisan_id = resp.json()["id"]

    client_headers = get_auth_headers(
        client, "vision-client@test.com", "Pass123!", "client"
    )
    return artisan_headers, artisan_id, client_headers


def create_in_progress_booking(client, artisan_headers, client_headers, artisan_id):
    booking_data = {
        "artisan_id": artisan_id,
        "service": "Replace the front porch steps with stone",
        "estimated_hours": 8,
        "estimated_cost": 1200.0,
        "date": "2026-04-01T10:00:00",
        "location": "123 Main St",
        "notes": "Finish the landing with matching stone.",
    }
    resp = client.post(
        "api/v1/bookings/create", json=booking_data, headers=client_headers
    )
    assert resp.status_code == 201
    booking_id = resp.json()["id"]

    resp = client.put(
        f"api/v1/bookings/{booking_id}/status",
        json={"status": "confirmed"},
        headers=artisan_headers,
    )
    assert resp.status_code == 200

    resp = client.put(
        f"api/v1/bookings/{booking_id}/status",
        json={"status": "in_progress"},
        headers=artisan_headers,
    )
    assert resp.status_code == 200

    return booking_id


def test_verify_completion_auto_closes_high_confidence_booking(client, db_session):
    artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
    booking_id = create_in_progress_booking(
        client, artisan_headers, client_headers, artisan_id
    )

    response = client.post(
        f"api/v1/bookings/{booking_id}/verify-completion",
        json={
            "scope_hash": "scopehash_stone_steps",
            "sow": "Replace the front porch steps with stone and finish the landing.",
            "after_photos": [
                "front porch steps stone landing complete",
                "stone steps with matching landing",
            ],
        },
        headers=artisan_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verified"] is True
    assert payload["completion_confidence"] >= 0.75
    assert payload["status"] == "completed"
    assert payload["missing_deliverables"] == []

    booking = db_session.query(Booking).filter(Booking.id == UUID(booking_id)).first()
    assert booking is not None
    assert booking.status.value == "completed"


def test_verify_completion_reports_wrong_materials(client):
    artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
    booking_id = create_in_progress_booking(
        client, artisan_headers, client_headers, artisan_id
    )

    response = client.post(
        f"api/v1/bookings/{booking_id}/verify-completion",
        json={
            "scope_hash": "scopehash_stone_steps",
            "sow": "Replace the front porch steps with stone and finish the landing.",
            "after_photos": ["wood deck installed"],
        },
        headers=artisan_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verified"] is False
    assert payload["completion_confidence"] < 0.75
    assert payload["status"] == "in_progress"
    assert payload["fundamentally_wrong"]
    assert payload["missing_deliverables"]