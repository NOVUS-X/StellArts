from datetime import datetime


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

    offline_resp = client.patch(
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

    online_resp = client.patch(
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
    resp = client.patch(
        "api/v1/artisans/availability",
        json={"is_available": False},
    )
    assert resp.status_code in (401, 403)


def test_artisan_availability_rejects_non_artisan(client):
    headers = get_auth_headers(client, "not-artisan@test.com", "Pass123!", "client")

    resp = client.patch(
        "api/v1/artisans/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert resp.status_code == 403
