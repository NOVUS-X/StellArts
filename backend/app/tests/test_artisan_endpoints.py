"""
Tests for previously-stub artisan endpoints:
  - DELETE /artisans/{artisan_id}
  - PUT /artisans/availability
  - GET /artisans/my-portfolio
  - POST /artisans/portfolio/add
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.db.session import get_db
from app.models.artisan import Artisan
from app.models.portfolio import Portfolio
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, email: str, password: str, role: str, full_name: str) -> dict:
    """Helper to register a user and return auth headers."""
    client.post(
        "api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name,
            "phone": "5550000001",
        },
    )
    resp = client.post("api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_artisan_profile(client, headers: dict) -> int:
    """Create an artisan profile and return its ID."""
    resp = client.post(
        "api/v1/artisans/profile",
        json={
            "business_name": "Test Business",
            "description": "Test description",
            "hourly_rate": 50.0,
            "specialties": ["plumbing"],
        },
        headers=headers,
    )
    assert resp.status_code == 200, f"Profile creation failed: {resp.text}"
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# DELETE /artisans/{artisan_id}
# ---------------------------------------------------------------------------

def test_delete_artisan_admin_removes_from_db(client):
    """Admin DELETE actually removes the artisan row from the database."""
    # Setup: artisan user + admin user
    artisan_headers = _register_and_login(client, "del_art@test.com", "Pass123!", "artisan", "Del Artisan")
    admin_headers = _register_and_login(client, "del_admin@test.com", "Pass123!", "admin", "Del Admin")

    artisan_id = _create_artisan_profile(client, artisan_headers)

    # Verify artisan exists before deletion
    resp = client.get(f"api/v1/artisans/{artisan_id}/profile")
    assert resp.status_code == 200

    # Delete — must be admin
    with patch("app.services.geolocation.geolocation_service.remove_artisan_location", new_callable=AsyncMock):
        resp = client.delete(f"api/v1/artisans/{artisan_id}", headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "deleted successfully" in body["message"]

    # Artisan must no longer exist
    resp = client.get(f"api/v1/artisans/{artisan_id}/profile")
    assert resp.status_code == 404


def test_delete_artisan_not_found_returns_404(client):
    """DELETE with a non-existent artisan ID returns 404."""
    admin_headers = _register_and_login(client, "del_admin2@test.com", "Pass123!", "admin", "Admin2")

    with patch("app.services.geolocation.geolocation_service.remove_artisan_location", new_callable=AsyncMock):
        resp = client.delete("api/v1/artisans/99999", headers=admin_headers)
    assert resp.status_code == 404


def test_delete_artisan_non_admin_returns_403(client):
    """Non-admin users cannot delete artisans."""
    artisan_headers = _register_and_login(client, "prot_art@test.com", "Pass123!", "artisan", "Prot Art")
    artisan_id = _create_artisan_profile(client, artisan_headers)

    resp = client.delete(f"api/v1/artisans/{artisan_id}", headers=artisan_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /artisans/availability
# ---------------------------------------------------------------------------

def test_update_availability_sets_is_available_false(client):
    """PUT /availability with is_available=false actually updates the DB."""
    headers = _register_and_login(client, "avail_art@test.com", "Pass123!", "artisan", "Avail Art")
    _create_artisan_profile(client, headers)

    resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_available"] is False


def test_update_availability_sets_is_available_true(client):
    """PUT /availability can toggle back to available."""
    headers = _register_and_login(client, "avail_art2@test.com", "Pass123!", "artisan", "Avail Art2")
    _create_artisan_profile(client, headers)

    # First set unavailable
    client.put("api/v1/artisans/availability", json={"is_available": False}, headers=headers)

    # Now set available again
    resp = client.put("api/v1/artisans/availability", json={"is_available": True}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_available"] is True


def test_update_availability_without_profile_returns_404(client):
    """PUT /availability when artisan has no profile returns 404."""
    # Register as artisan but DO NOT create a profile
    headers = _register_and_login(client, "avail_noprofile@test.com", "Pass123!", "artisan", "No Profile")

    resp = client.put("api/v1/artisans/availability", json={"is_available": False}, headers=headers)
    assert resp.status_code == 404


def test_update_availability_requires_authentication(client):
    """PUT /availability without a token is rejected."""
    resp = client.put("api/v1/artisans/availability", json={"is_available": False})
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /artisans/my-portfolio
# ---------------------------------------------------------------------------

def test_get_my_portfolio_empty_when_no_items(client):
    """GET /my-portfolio returns an empty list for a new artisan."""
    headers = _register_and_login(client, "port_art@test.com", "Pass123!", "artisan", "Port Art")
    _create_artisan_profile(client, headers)

    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "portfolio_items" in body
    assert body["portfolio_items"] == []


def test_get_my_portfolio_returns_real_items(client):
    """GET /my-portfolio returns items that were previously added."""
    headers = _register_and_login(client, "port_art2@test.com", "Pass123!", "artisan", "Port Art2")
    _create_artisan_profile(client, headers)

    # Add an item
    client.post(
        "api/v1/artisans/portfolio/add",
        json={"title": "My Work", "image": "https://example.com/img.jpg"},
        headers=headers,
    )

    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["portfolio_items"]
    assert len(items) == 1
    assert items[0]["title"] == "My Work"
    assert items[0]["image"] == "https://example.com/img.jpg"


def test_get_my_portfolio_without_profile_returns_404(client):
    """GET /my-portfolio when artisan has no profile returns 404."""
    headers = _register_and_login(client, "port_noprofile@test.com", "Pass123!", "artisan", "No Profile2")

    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /artisans/portfolio/add
# ---------------------------------------------------------------------------

def test_add_portfolio_item_stores_in_db(client):
    """POST /portfolio/add creates a real Portfolio row."""
    headers = _register_and_login(client, "add_port@test.com", "Pass123!", "artisan", "Add Port")
    _create_artisan_profile(client, headers)

    resp = client.post(
        "api/v1/artisans/portfolio/add",
        json={"title": "Bathroom Remodel", "image": "https://cdn.example.com/photo.jpg"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Bathroom Remodel"
    assert body["image"] == "https://cdn.example.com/photo.jpg"
    assert "id" in body


def test_add_portfolio_item_without_title(client):
    """POST /portfolio/add title is optional — image is required."""
    headers = _register_and_login(client, "add_port2@test.com", "Pass123!", "artisan", "Add Port2")
    _create_artisan_profile(client, headers)

    resp = client.post(
        "api/v1/artisans/portfolio/add",
        json={"image": "https://cdn.example.com/photo2.jpg"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] is None


def test_add_portfolio_item_missing_image_returns_422(client):
    """POST /portfolio/add without required image field returns 422."""
    headers = _register_and_login(client, "add_port3@test.com", "Pass123!", "artisan", "Add Port3")
    _create_artisan_profile(client, headers)

    resp = client.post(
        "api/v1/artisans/portfolio/add",
        json={"title": "No image here"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_add_portfolio_item_without_profile_returns_404(client):
    """POST /portfolio/add when artisan has no profile returns 404."""
    headers = _register_and_login(client, "add_noprofile@test.com", "Pass123!", "artisan", "No Profile3")

    resp = client.post(
        "api/v1/artisans/portfolio/add",
        json={"image": "https://example.com/x.jpg"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_add_multiple_portfolio_items(client):
    """Adding multiple items accumulates correctly in the portfolio."""
    headers = _register_and_login(client, "multi_port@test.com", "Pass123!", "artisan", "Multi Port")
    _create_artisan_profile(client, headers)

    client.post("api/v1/artisans/portfolio/add", json={"title": "Item 1", "image": "https://ex.com/1.jpg"}, headers=headers)
    client.post("api/v1/artisans/portfolio/add", json={"title": "Item 2", "image": "https://ex.com/2.jpg"}, headers=headers)
    client.post("api/v1/artisans/portfolio/add", json={"title": "Item 3", "image": "https://ex.com/3.jpg"}, headers=headers)

    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["portfolio_items"]
    assert len(items) == 3
