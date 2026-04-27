"""
Issue #204 – Expand Test Coverage for Portfolio Management
==========================================================
Tests cover:
  - GET  /api/v1/artisans/my-portfolio  (list)
  - POST /api/v1/artisans/portfolio/add (create via URL)
  - PUT  /api/v1/artisans/portfolio/{id} (update)
  - DELETE /api/v1/artisans/portfolio/{id} (delete)
  - POST /api/v1/artisans/portfolio/upload (image upload + URL generation)
"""

from __future__ import annotations

import io

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ARTISAN_EMAIL = "portfolio_artisan@example.com"
_ARTISAN_PASS = "ArtisanPass1!"


def _register_and_login(client) -> dict:
    """Register an artisan user, create their profile, and return auth headers."""
    # 1. Register
    client.post(
        "api/v1/auth/register",
        json={
            "email": _ARTISAN_EMAIL,
            "password": _ARTISAN_PASS,
            "role": "artisan",
            "full_name": "Portfolio Artisan",
            "username": "portfolio_artisan",
        },
    )

    # 2. Login
    resp = client.post(
        "api/v1/auth/login",
        json={"email": _ARTISAN_EMAIL, "password": _ARTISAN_PASS},
    )
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 3. Create artisan profile (required for portfolio endpoints)
    client.post(
        "api/v1/artisans/profile",
        json={
            "business_name": "Test Workshop",
            "description": "A test artisan",
            "specialties": ["plumbing"],
            "experience_years": 3,
            "hourly_rate": 50.0,
            "location": "Lagos",
        },
        headers=headers,
    )

    return headers


def _add_item(
    client, headers, title="My Work", image_url="https://example.com/img.jpg"
):
    """Helper: add a portfolio item and return the response."""
    return client.post(
        "api/v1/artisans/portfolio/add",
        params={"title": title, "image_url": image_url},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# GET /my-portfolio
# ---------------------------------------------------------------------------


def test_get_portfolio_empty(client):
    """Newly created artisan has an empty portfolio."""
    headers = _register_and_login(client)
    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "portfolio_items" in data
    assert data["portfolio_items"] == []


def test_get_portfolio_requires_auth(client):
    """Unauthenticated request is rejected."""
    resp = client.get("api/v1/artisans/my-portfolio")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /portfolio/add  (create via URL)
# ---------------------------------------------------------------------------


def test_add_portfolio_item(client):
    """Artisan can add a portfolio item with a URL."""
    headers = _register_and_login(client)
    resp = _add_item(client, headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Work"
    assert data["image"] == "https://example.com/img.jpg"
    assert "id" in data
    assert "artisan_id" in data


def test_add_portfolio_item_appears_in_list(client):
    """Added item shows up in GET /my-portfolio."""
    headers = _register_and_login(client)
    _add_item(
        client, headers, title="Tile Work", image_url="https://cdn.example.com/tile.jpg"
    )

    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["portfolio_items"]
    assert len(items) == 1
    assert items[0]["title"] == "Tile Work"
    assert items[0]["image"] == "https://cdn.example.com/tile.jpg"


def test_add_portfolio_item_missing_image_url(client):
    """Creating an item without image_url returns 422."""
    headers = _register_and_login(client)
    resp = client.post(
        "api/v1/artisans/portfolio/add",
        params={"title": "No Image"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_add_multiple_portfolio_items(client):
    """Multiple items can be added and all appear in the list."""
    headers = _register_and_login(client)
    for i in range(3):
        _add_item(
            client, headers, title=f"Item {i}", image_url=f"https://example.com/{i}.jpg"
        )

    resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["portfolio_items"]) == 3


def test_add_portfolio_item_requires_auth(client):
    """Unauthenticated add is rejected."""
    resp = client.post(
        "api/v1/artisans/portfolio/add",
        params={"title": "Hack", "image_url": "https://example.com/hack.jpg"},
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PUT /portfolio/{item_id}  (update)
# ---------------------------------------------------------------------------


def test_update_portfolio_item_title(client):
    """Artisan can update the title of their portfolio item."""
    headers = _register_and_login(client)
    add_resp = _add_item(client, headers)
    item_id = add_resp.json()["id"]

    resp = client.put(
        f"api/v1/artisans/portfolio/{item_id}",
        params={"title": "Updated Title"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


def test_update_portfolio_item_image_url(client):
    """Artisan can update the image URL of their portfolio item."""
    headers = _register_and_login(client)
    add_resp = _add_item(client, headers)
    item_id = add_resp.json()["id"]

    new_url = "https://example.com/new_image.jpg"
    resp = client.put(
        f"api/v1/artisans/portfolio/{item_id}",
        params={"image_url": new_url},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["image"] == new_url


def test_update_nonexistent_portfolio_item(client):
    """Updating a non-existent item returns 404."""
    headers = _register_and_login(client)
    resp = client.put(
        "api/v1/artisans/portfolio/99999",
        params={"title": "Ghost"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_update_portfolio_item_requires_auth(client):
    """Unauthenticated update is rejected."""
    resp = client.put("api/v1/artisans/portfolio/1", params={"title": "Hack"})
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# DELETE /portfolio/{item_id}
# ---------------------------------------------------------------------------


def test_delete_portfolio_item(client):
    """Artisan can delete their own portfolio item."""
    headers = _register_and_login(client)
    add_resp = _add_item(client, headers)
    item_id = add_resp.json()["id"]

    del_resp = client.delete(f"api/v1/artisans/portfolio/{item_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify it no longer appears in the list
    list_resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["portfolio_items"] == []


def test_delete_nonexistent_portfolio_item(client):
    """Deleting a non-existent item returns 404."""
    headers = _register_and_login(client)
    resp = client.delete("api/v1/artisans/portfolio/99999", headers=headers)
    assert resp.status_code == 404


def test_delete_portfolio_item_requires_auth(client):
    """Unauthenticated delete is rejected."""
    resp = client.delete("api/v1/artisans/portfolio/1")
    assert resp.status_code in (401, 403)


def test_delete_removes_only_target_item(client):
    """Deleting one item does not affect other items."""
    headers = _register_and_login(client)
    id1 = _add_item(
        client, headers, title="Keep", image_url="https://example.com/keep.jpg"
    ).json()["id"]
    id2 = _add_item(
        client, headers, title="Remove", image_url="https://example.com/remove.jpg"
    ).json()["id"]

    client.delete(f"api/v1/artisans/portfolio/{id2}", headers=headers)

    list_resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    items = list_resp.json()["portfolio_items"]
    assert len(items) == 1
    assert items[0]["id"] == id1


# ---------------------------------------------------------------------------
# POST /portfolio/upload  (image upload + URL generation)
# ---------------------------------------------------------------------------


def test_upload_portfolio_image(client):
    """Artisan can upload an image file; a URL is generated and stored."""
    headers = _register_and_login(client)

    fake_image = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    resp = client.post(
        "api/v1/artisans/portfolio/upload",
        params={"title": "Uploaded Work"},
        files={"file": ("photo.png", fake_image, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "image_url" in data
    assert data["image_url"].startswith("/uploads/")
    assert data["image_url"].endswith(".png")
    assert data["title"] == "Uploaded Work"


def test_upload_portfolio_image_appears_in_list(client):
    """Uploaded image item appears in GET /my-portfolio."""
    headers = _register_and_login(client)

    fake_image = io.BytesIO(b"FAKEJPEG" + b"\x00" * 50)
    client.post(
        "api/v1/artisans/portfolio/upload",
        params={"title": "Uploaded Tile"},
        files={"file": ("tile.jpg", fake_image, "image/jpeg")},
        headers=headers,
    )

    list_resp = client.get("api/v1/artisans/my-portfolio", headers=headers)
    items = list_resp.json()["portfolio_items"]
    assert len(items) == 1
    assert items[0]["title"] == "Uploaded Tile"
    assert items[0]["image"].startswith("/uploads/")


def test_upload_portfolio_image_url_is_unique(client):
    """Each upload generates a unique URL."""
    headers = _register_and_login(client)

    urls = set()
    for _ in range(3):
        fake_image = io.BytesIO(b"FAKEDATA")
        resp = client.post(
            "api/v1/artisans/portfolio/upload",
            params={"title": "Work"},
            files={"file": ("img.jpg", fake_image, "image/jpeg")},
            headers=headers,
        )
        assert resp.status_code == 201
        urls.add(resp.json()["image_url"])

    assert len(urls) == 3, "Each upload should produce a unique URL"


def test_upload_portfolio_image_missing_file(client):
    """Upload without a file returns 422."""
    headers = _register_and_login(client)
    resp = client.post(
        "api/v1/artisans/portfolio/upload",
        params={"title": "No File"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_upload_portfolio_image_requires_auth(client):
    """Unauthenticated upload is rejected."""
    fake_image = io.BytesIO(b"FAKEDATA")
    resp = client.post(
        "api/v1/artisans/portfolio/upload",
        files={"file": ("img.jpg", fake_image, "image/jpeg")},
    )
    assert resp.status_code in (401, 403)
