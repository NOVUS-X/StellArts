"""
Unit tests for booking state machine rules.

These tests verify:
1. Only artisan can mark a booking as Confirmed (PENDING -> CONFIRMED)
2. Only client can mark a booking as Completed (CONFIRMED -> COMPLETED)
3. Cancellation rules based on current state and user role
"""

import pytest
from uuid import uuid4


def get_auth_headers(client, email, password, role):
    """Helper to get auth headers for a user."""
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


def create_artisan_and_client(client):
    """Helper to create an artisan and client with profiles."""
    # Create artisan
    artisan_headers = get_auth_headers(client, "artisan@test.com", "Pass123!", "artisan")
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

    # Create client
    client_headers = get_auth_headers(client, "client@test.com", "Pass123!", "client")

    return artisan_headers, artisan_id, client_headers


def create_booking(client, client_headers, artisan_id):
    """Helper to create a booking."""
    booking_data = {
        "artisan_id": artisan_id,
        "service_description": "Fix my sink",
        "estimated_hours": 2,
        "estimated_cost": 100.0,
        "scheduled_date": "2024-12-25T10:00:00",
        "location": "123 Main St",
        "notes": "Urgent",
    }
    resp = client.post(
        "api/v1/bookings/create", json=booking_data, headers=client_headers
    )
    assert resp.status_code == 200
    return resp.json()["booking_id"]


class TestPendingToConfirmed:
    """Tests for PENDING -> CONFIRMED transition."""

    def test_artisan_can_confirm_pending_booking(self, client):
        """Artisan should be able to confirm a pending booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Artisan confirms the booking
        status_update = {"status": "confirmed"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=artisan_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "confirmed"

    def test_client_cannot_confirm_pending_booking(self, client):
        """Client should NOT be able to confirm a pending booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Client tries to confirm the booking
        status_update = {"status": "confirmed"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=client_headers,
        )
        assert resp.status_code == 403
        assert "only the artisan can confirm" in resp.json()["detail"].lower()


class TestConfirmedToCompleted:
    """Tests for CONFIRMED -> COMPLETED transition."""

    def test_client_can_complete_confirmed_booking(self, client):
        """Client should be able to mark a confirmed booking as completed."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # First, artisan confirms the booking
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=artisan_headers,
        )
        assert resp.status_code == 200

        # Client marks the booking as completed
        status_update = {"status": "completed"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=client_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "completed"

    def test_artisan_cannot_complete_confirmed_booking(self, client):
        """Artisan should NOT be able to mark a confirmed booking as completed."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # First, artisan confirms the booking
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=artisan_headers,
        )
        assert resp.status_code == 200

        # Artisan tries to mark the booking as completed
        status_update = {"status": "completed"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=artisan_headers,
        )
        assert resp.status_code == 403
        assert "only the client can mark" in resp.json()["detail"].lower()


class TestCancellationRules:
    """Tests for cancellation rules."""

    def test_client_can_cancel_pending_booking(self, client):
        """Client should be able to cancel a pending booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Client cancels the pending booking
        status_update = {"status": "cancelled"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=client_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "cancelled"

    def test_artisan_can_cancel_pending_booking(self, client):
        """Artisan should be able to cancel a pending booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Artisan cancels the pending booking
        status_update = {"status": "cancelled"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=artisan_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "cancelled"

    def test_artisan_can_cancel_confirmed_booking(self, client):
        """Artisan should be able to cancel a confirmed booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # First, artisan confirms the booking
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=artisan_headers,
        )
        assert resp.status_code == 200

        # Artisan cancels the confirmed booking
        status_update = {"status": "cancelled"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=artisan_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "cancelled"

    def test_client_cannot_cancel_confirmed_booking(self, client):
        """Client should NOT be able to cancel a confirmed booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # First, artisan confirms the booking
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=artisan_headers,
        )
        assert resp.status_code == 200

        # Client tries to cancel the confirmed booking
        status_update = {"status": "cancelled"}
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json=status_update,
            headers=client_headers,
        )
        assert resp.status_code == 403
        assert "clients can only cancel pending" in resp.json()["detail"].lower()


class TestInvalidTransitions:
    """Tests for invalid state transitions."""

    def test_cannot_confirm_already_confirmed_booking(self, client):
        """Should not be able to confirm an already confirmed booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Artisan confirms the booking
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=artisan_headers,
        )
        assert resp.status_code == 200

        # Try to confirm again
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=artisan_headers,
        )
        assert resp.status_code == 400
        assert "cannot confirm" in resp.json()["detail"].lower()

    def test_cannot_complete_pending_booking(self, client):
        """Should not be able to complete a pending booking directly."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Client tries to complete pending booking
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "completed"},
            headers=client_headers,
        )
        assert resp.status_code == 400
        assert "cannot complete" in resp.json()["detail"].lower()

    def test_cannot_complete_already_completed_booking(self, client):
        """Should not be able to complete an already completed booking."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Artisan confirms
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=artisan_headers,
        )
        assert resp.status_code == 200

        # Client completes
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "completed"},
            headers=client_headers,
        )
        assert resp.status_code == 200

        # Try to complete again
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "completed"},
            headers=client_headers,
        )
        assert resp.status_code == 400
        assert "cannot complete" in resp.json()["detail"].lower()


class TestUnauthorizedAccess:
    """Tests for unauthorized access to bookings."""

    def test_unrelated_user_cannot_update_booking(self, client):
        """A user not associated with the booking cannot update it."""
        artisan_headers, artisan_id, client_headers = create_artisan_and_client(client)
        booking_id = create_booking(client, client_headers, artisan_id)

        # Create another artisan
        other_artisan_headers = get_auth_headers(
            client, "other_artisan@test.com", "Pass123!", "artisan"
        )
        other_artisan_profile = {
            "business_name": "Other Artisan Services",
            "description": "Other services",
            "hourly_rate": 60.0,
            "specialties": ["electrical"],
        }
        resp = client.post(
            "api/v1/artisans/profile",
            json=other_artisan_profile,
            headers=other_artisan_headers,
        )
        assert resp.status_code == 200

        # Other artisan tries to update the booking
        resp = client.put(
            f"api/v1/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=other_artisan_headers,
        )
        assert resp.status_code == 403
        assert "not authorized" in resp.json()["detail"].lower()
