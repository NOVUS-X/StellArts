"""Tests for Open Requests CRUD endpoints."""
from app.tests.conftest import TestingSessionLocal


def get_auth_headers(client, email, password, role):
    """Helper to register, login and get auth headers."""
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


def create_client_profile(client, client_headers):
    """Helper to create a client profile."""
    from app.core.security import decode_token
    from app.models.client import Client

    db = TestingSessionLocal()
    try:
        token = client_headers["Authorization"].split(" ")[1]
        payload = decode_token(token)
        user_id = int(payload["sub"])

        client_profile = db.query(Client).filter(Client.user_id == user_id).first()
        if not client_profile:
            client_profile = Client(user_id=user_id, address="123 Test St")
            db.add(client_profile)
            db.commit()
            db.refresh(client_profile)
        return client_profile.id
    finally:
        db.close()


class TestOpenRequestCreate:
    """Tests for POST /api/v1/requests"""

    def test_create_open_request_success(self, client):
        """Test successful creation of an open request."""
        headers = get_auth_headers(client, "client@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        request_data = {
            "title": "Fix kitchen sink",
            "description": "Need a plumber to fix a leaking kitchen sink",
            "budget": 150.00,
            "location_lat": 40.7128,
            "location_lng": -74.0060,
        }

        resp = client.post("api/v1/requests", json=request_data, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == request_data["title"]
        assert data["description"] == request_data["description"]
        assert data["budget"] == request_data["budget"]
        assert data["status"] == "open"
        assert "id" in data
        assert "created_at" in data

    def test_create_open_request_minimal(self, client):
        """Test creation with only required fields."""
        headers = get_auth_headers(client, "client2@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        request_data = {"title": "Simple job"}

        resp = client.post("api/v1/requests", json=request_data, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Simple job"
        assert data["description"] is None
        assert data["budget"] is None

    def test_create_open_request_unauthenticated(self, client):
        """Test that unauthenticated users cannot create requests."""
        request_data = {"title": "Fix something"}

        resp = client.post("api/v1/requests", json=request_data)
        assert resp.status_code in (401, 403)

    def test_create_open_request_artisan_forbidden(self, client):
        """Test that artisans cannot create open requests."""
        headers = get_auth_headers(client, "artisan@test.com", "Pass123!", "artisan")

        request_data = {"title": "Fix something"}

        resp = client.post("api/v1/requests", json=request_data, headers=headers)
        assert resp.status_code == 403

    def test_create_open_request_invalid_location(self, client):
        """Test that invalid location coordinates are rejected."""
        headers = get_auth_headers(client, "client3@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        # Invalid latitude (> 90)
        request_data = {
            "title": "Test",
            "location_lat": 100.0,  # Invalid
            "location_lng": -74.0,
        }

        resp = client.post("api/v1/requests", json=request_data, headers=headers)
        assert resp.status_code == 422


class TestOpenRequestList:
    """Tests for GET /api/v1/requests"""

    def test_list_open_requests_empty(self, client):
        """Test listing when no requests exist."""
        resp = client.get("api/v1/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_open_requests_with_data(self, client):
        """Test listing open requests."""
        # Create some requests
        headers = get_auth_headers(client, "client_list@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        for i in range(3):
            request_data = {
                "title": f"Job {i}",
                "description": f"Description {i}",
                "budget": 100 + i * 50,
            }
            client.post("api/v1/requests", json=request_data, headers=headers)

        resp = client.get("api/v1/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_open_requests_location_filter(self, client):
        """Test location-based filtering."""
        headers = get_auth_headers(client, "client_loc@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        # Create requests at different locations
        # NYC area
        client.post(
            "api/v1/requests",
            json={
                "title": "NYC Job",
                "location_lat": 40.7128,
                "location_lng": -74.0060,
            },
            headers=headers,
        )

        # LA area (far from NYC)
        client.post(
            "api/v1/requests",
            json={
                "title": "LA Job",
                "location_lat": 34.0522,
                "location_lng": -118.2437,
            },
            headers=headers,
        )

        # Search near NYC with small radius
        resp = client.get("api/v1/requests?lat=40.7128&lng=-74.0060&radius_km=10")
        assert resp.status_code == 200
        data = resp.json()
        # Should only find the NYC job
        assert data["total"] >= 1
        titles = [item["title"] for item in data["items"]]
        assert "NYC Job" in titles

    def test_list_open_requests_pagination(self, client):
        """Test pagination."""
        headers = get_auth_headers(client, "client_page@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        # Create 5 requests
        for i in range(5):
            client.post(
                "api/v1/requests",
                json={"title": f"Job {i}"},
                headers=headers,
            )

        # Get first page
        resp = client.get("api/v1/requests?skip=0&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

        # Get second page
        resp = client.get("api/v1/requests?skip=2&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2


class TestOpenRequestGet:
    """Tests for GET /api/v1/requests/{id}"""

    def test_get_open_request_success(self, client):
        """Test getting a specific open request."""
        headers = get_auth_headers(client, "client_get@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        # Create a request
        create_resp = client.post(
            "api/v1/requests",
            json={"title": "Get Test Job"},
            headers=headers,
        )
        request_id = create_resp.json()["id"]

        # Get the request
        resp = client.get(f"api/v1/requests/{request_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == request_id
        assert data["title"] == "Get Test Job"

    def test_get_open_request_not_found(self, client):
        """Test getting a non-existent request."""
        resp = client.get("api/v1/requests/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_open_request_invalid_uuid(self, client):
        """Test getting a request with invalid UUID format."""
        resp = client.get("api/v1/requests/not-a-uuid")
        assert resp.status_code == 422  # FastAPI validation error


class TestOpenRequestUpdate:
    """Tests for PUT /api/v1/requests/{id}"""

    def test_update_open_request_success(self, client):
        """Test successful update of an open request."""
        headers = get_auth_headers(client, "client_upd@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        # Create a request
        create_resp = client.post(
            "api/v1/requests",
            json={"title": "Original Title"},
            headers=headers,
        )
        request_id = create_resp.json()["id"]

        # Update the request
        update_data = {
            "title": "Updated Title",
            "description": "Updated description",
            "budget": 200.00,
        }
        resp = client.put(
            f"api/v1/requests/{request_id}", json=update_data, headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["description"] == "Updated description"
        assert data["budget"] == 200.00

    def test_update_open_request_status(self, client):
        """Test updating the status of an open request."""
        headers = get_auth_headers(
            client, "client_status@test.com", "Pass123!", "client"
        )
        create_client_profile(client, headers)

        # Create a request
        create_resp = client.post(
            "api/v1/requests",
            json={"title": "Status Test"},
            headers=headers,
        )
        request_id = create_resp.json()["id"]

        # Update status to closed
        resp = client.put(
            f"api/v1/requests/{request_id}",
            json={"status": "closed"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    def test_update_open_request_not_owner(self, client):
        """Test that non-owners cannot update requests."""
        # Create request with one user
        headers1 = get_auth_headers(client, "owner@test.com", "Pass123!", "client")
        create_client_profile(client, headers1)

        create_resp = client.post(
            "api/v1/requests",
            json={"title": "Owner's Job"},
            headers=headers1,
        )
        request_id = create_resp.json()["id"]

        # Try to update with another user
        headers2 = get_auth_headers(client, "other@test.com", "Pass123!", "client")
        create_client_profile(client, headers2)

        resp = client.put(
            f"api/v1/requests/{request_id}",
            json={"title": "Hacked"},
            headers=headers2,
        )
        assert resp.status_code == 404


class TestOpenRequestDelete:
    """Tests for DELETE /api/v1/requests/{id}"""

    def test_delete_open_request_success(self, client):
        """Test successful deletion of an open request."""
        headers = get_auth_headers(client, "client_del@test.com", "Pass123!", "client")
        create_client_profile(client, headers)

        # Create a request
        create_resp = client.post(
            "api/v1/requests",
            json={"title": "To Delete"},
            headers=headers,
        )
        request_id = create_resp.json()["id"]

        # Delete the request
        resp = client.delete(f"api/v1/requests/{request_id}", headers=headers)
        assert resp.status_code == 204

        # Verify it's gone
        resp = client.get(f"api/v1/requests/{request_id}")
        assert resp.status_code == 404

    def test_delete_open_request_not_owner(self, client):
        """Test that non-owners cannot delete requests."""
        # Create request with one user
        headers1 = get_auth_headers(client, "del_owner@test.com", "Pass123!", "client")
        create_client_profile(client, headers1)

        create_resp = client.post(
            "api/v1/requests",
            json={"title": "Owner's Job"},
            headers=headers1,
        )
        request_id = create_resp.json()["id"]

        # Try to delete with another user
        headers2 = get_auth_headers(client, "del_other@test.com", "Pass123!", "client")
        create_client_profile(client, headers2)

        resp = client.delete(f"api/v1/requests/{request_id}", headers=headers2)
        assert resp.status_code == 404
