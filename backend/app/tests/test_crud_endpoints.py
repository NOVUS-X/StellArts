import pytest
from app.models.artisan import Artisan
from app.models.client import Client
from app.models.booking import Booking, BookingStatus

def get_auth_headers(client, email, password, role):
    # Register
    client.post("api/v1/auth/register", json={
        "email": email,
        "password": password,
        "role": role,
        "full_name": f"Test {role.capitalize()}",
        "phone": "9999999999"
    })
    # Login
    login_resp = client.post("api/v1/auth/login", json={
        "email": email,
        "password": password
    })
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
        "specialties": ["plumbing"]
    }
    resp = client.post("api/v1/artisans/profile", json=artisan_profile, headers=artisan_headers)
    assert resp.status_code == 200
    artisan_id = resp.json()["id"]

    # 2. Create Client and Booking
    client_headers = get_auth_headers(client, "cli@test.com", "Pass123!", "client")
    
    booking_data = {
        "artisan_id": artisan_id,
        "service_description": "Fix my sink",
        "estimated_hours": 2,
        "estimated_cost": 100.0,
        "scheduled_date": "2024-12-25T10:00:00",
        "location": "123 Main St",
        "notes": "Urgent"
    }
    resp = client.post("api/v1/bookings/create", json=booking_data, headers=client_headers)
    assert resp.status_code == 200
    booking_id = resp.json()["booking_id"]
    
    # 3. Verify Client Bookings
    resp = client.get("api/v1/bookings/my-bookings", headers=client_headers)
    assert resp.status_code == 200
    bookings = resp.json()["bookings"]
    assert len(bookings) == 1
    assert bookings[0]["id"] == booking_id
    
    # 4. Verify Artisan Bookings
    resp = client.get("api/v1/artisans/my-bookings", headers=artisan_headers)
    assert resp.status_code == 200
    bookings = resp.json()["bookings"]
    assert len(bookings) == 1
    assert bookings[0]["id"] == booking_id
    
    # 5. Artisan accepts booking
    status_update = {"status": "confirmed"}
    resp = client.put(f"api/v1/bookings/{booking_id}/status", json=status_update, headers=artisan_headers)
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "confirmed"
    
    # 6. Verify status change
    resp = client.get("api/v1/bookings/my-bookings", headers=client_headers)
    assert resp.json()["bookings"][0]["status"] == "confirmed"

def test_artisan_profile_crud(client):
    headers = get_auth_headers(client, "art2@test.com", "Pass123!", "artisan")
    
    # Create
    profile_data = {
        "business_name": "New Biz",
        "specialties": ["painting"]
    }
    resp = client.post("api/v1/artisans/profile", json=profile_data, headers=headers)
    assert resp.status_code == 200
    art_id = resp.json()["id"]
    
    # Get Public Profile
    resp = client.get(f"api/v1/artisans/{art_id}/profile")
    assert resp.status_code == 200
    assert resp.json()["profile"]["business_name"] == "New Biz"
