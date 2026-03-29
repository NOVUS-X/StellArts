"""Tests for previously-stub artisan endpoints (Issue #142C)."""
from app.db.session import get_db
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, email, role="artisan"):
    client.post(
        "api/v1/auth/register",
        json={"email": email, "password": "StrongPass1!", "role": role},
    )
    resp = client.post(
        "api/v1/auth/login",
        json={"email": email, "password": "StrongPass1!"},
    )
    return resp.json()


def _create_artisan_profile(client, headers):
    return client.post(
        "api/v1/artisans/profile",
        json={
            "business_name": "Test Artisan",
            "description": "A skilled craftsperson",
            "specialties": ["carpentry"],
            "hourly_rate": "50.00",
        },
        headers=headers,
    )


def _promote_to_admin(client, email):
    """Promote a registered user to admin role directly via the test DB session."""
    db = next(client.app.dependency_overrides[get_db]())
    user = db.query(User).filter(User.email == email).first()
    user.role = "admin"
    db.commit()
    # Re-login to get a fresh token (role is read from DB on each request, so
    # existing token works too — but re-login keeps things explicit).
    resp = client.post(
        "api/v1/auth/login",
        json={"email": email, "password": "StrongPass1!"},
    )
    return resp.json()


# ---------------------------------------------------------------------------
# DELETE /artisans/{id}
# ---------------------------------------------------------------------------

def test_delete_artisan_returns_404_for_nonexistent(client):
    """Deleting a non-existent artisan ID returns 404."""
    _register_and_login(client, "admin_del404@example.com", role="artisan")
    admin_tokens = _promote_to_admin(client, "admin_del404@example.com")
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    resp = client.delete("api/v1/artisans/99999", headers=headers)
    assert resp.status_code == 404


def test_delete_artisan_actually_removes_from_db(client):
    """DELETE /artisans/{id} must remove the artisan record; subsequent GET returns 404."""
    # Create artisan
    artisan_tokens = _register_and_login(client, "artisan_to_del@example.com", role="artisan")
    artisan_headers = {"Authorization": f"Bearer {artisan_tokens['access_token']}"}
    profile_resp = _create_artisan_profile(client, artisan_headers)
    assert profile_resp.status_code == 200
    artisan_id = profile_resp.json()["id"]

    # Create admin
    _register_and_login(client, "admin_for_del@example.com", role="artisan")
    admin_tokens = _promote_to_admin(client, "admin_for_del@example.com")
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    # Delete
    del_resp = client.delete(f"api/v1/artisans/{artisan_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    # Verify it's gone
    get_resp = client.get(f"api/v1/artisans/{artisan_id}/profile")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /artisans/availability
# ---------------------------------------------------------------------------

def test_update_availability_persists_to_db(client):
    """PUT /artisans/availability should update is_available in the DB."""
    tokens = _register_and_login(client, "avail_test@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    _create_artisan_profile(client, headers)

    resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_available"] is False

    # Toggle back
    resp2 = client.put(
        "api/v1/artisans/availability",
        json={"is_available": True},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_available"] is True


def test_update_availability_requires_artisan_role(client):
    """PUT /artisans/availability must reject non-artisan users with 403."""
    tokens = _register_and_login(client, "client_avail@example.com", role="client")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert resp.status_code == 403


def test_update_availability_requires_artisan_profile(client):
    """Artisan without a profile should get 404 on availability update."""
    tokens = _register_and_login(client, "no_profile_avail@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.put(
        "api/v1/artisans/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Portfolio endpoints
# ---------------------------------------------------------------------------

def test_get_portfolio_returns_empty_initially(client):
    """GET /artisans/my-portfolio returns an empty list for a new artisan."""
    tokens = _register_and_login(client, "portfolio_empty@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    _create_artisan_profile(client, headers)

    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["portfolio_items"] == []


def test_add_portfolio_item_stores_in_db(client):
    """POST /artisans/portfolio/add should create a real Portfolio record,
    which then appears in GET /artisans/my-portfolio.
    """
    tokens = _register_and_login(client, "portfolio_add@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    _create_artisan_profile(client, headers)

    add_resp = client.post(
        "api/v1/artisans/portfolio/add",
        json={"title": "My First Project", "image": "https://example.com/img.jpg"},
        headers=headers,
    )
    assert add_resp.status_code == 201
    item = add_resp.json()
    assert item["title"] == "My First Project"
    assert item["image"] == "https://example.com/img.jpg"
    assert "id" in item

    # Verify it shows up in GET /my-portfolio
    get_resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert get_resp.status_code == 200
    items = get_resp.json()["portfolio_items"]
    assert len(items) == 1
    assert items[0]["id"] == item["id"]


def test_portfolio_requires_artisan_profile(client):
    """GET /artisans/my-portfolio returns 404 when no artisan profile exists."""
    tokens = _register_and_login(client, "no_profile_portfolio@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 404
