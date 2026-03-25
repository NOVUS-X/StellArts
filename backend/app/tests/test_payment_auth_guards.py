"""Tests for authentication guards on payment endpoints (Issue #142B)."""


def _register_and_login(client, email, role="client"):
    client.post(
        "api/v1/auth/register",
        json={"email": email, "password": "StrongPass1!", "role": role},
    )
    resp = client.post(
        "api/v1/auth/login",
        json={"email": email, "password": "StrongPass1!"},
    )
    return resp.json()


def test_unauthenticated_release_returns_401(client):
    """Unauthenticated POST /payments/release must return 401."""
    resp = client.post(
        "api/v1/payments/release",
        json={
            "booking_id": "some-booking-id",
            "artisan_public": "GARTISAN",
            "amount": "10.00",
        },
    )
    assert resp.status_code == 401


def test_unauthenticated_refund_returns_401(client):
    """Unauthenticated POST /payments/refund must return 401."""
    resp = client.post(
        "api/v1/payments/refund",
        json={
            "booking_id": "some-booking-id",
            "client_public": "GCLIENT",
            "amount": "10.00",
        },
    )
    assert resp.status_code == 401


def test_non_admin_release_returns_403(client):
    """A client (non-admin) calling /payments/release must get 403."""
    tokens = _register_and_login(client, "client_release@example.com", role="client")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.post(
        "api/v1/payments/release",
        json={
            "booking_id": "some-booking-id",
            "artisan_public": "GARTISAN",
            "amount": "10.00",
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_non_admin_refund_returns_403(client):
    """A client (non-admin) calling /payments/refund must get 403."""
    tokens = _register_and_login(client, "client_refund@example.com", role="client")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.post(
        "api/v1/payments/refund",
        json={
            "booking_id": "some-booking-id",
            "client_public": "GCLIENT",
            "amount": "10.00",
        },
        headers=headers,
    )
    assert resp.status_code == 403
