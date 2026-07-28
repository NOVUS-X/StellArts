"""Tests for WebSocket tracking endpoint."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.websockets import WebSocketDisconnect

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
    return {"Authorization": f"Bearer {token}"}, token


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


def create_artisan_profile(client, artisan_headers):
    """Helper to create an artisan profile."""
    from app.core.security import decode_token
    from app.models.artisan import Artisan

    db = TestingSessionLocal()
    try:
        token = artisan_headers["Authorization"].split(" ")[1]
        payload = decode_token(token)
        user_id = int(payload["sub"])

        artisan_profile = db.query(Artisan).filter(Artisan.user_id == user_id).first()
        if not artisan_profile:
            artisan_profile = Artisan(
                user_id=user_id,
                business_name="Test Artisan Services",
                specialties="plumbing",
            )
            db.add(artisan_profile)
            db.commit()
            db.refresh(artisan_profile)
        return artisan_profile.id
    finally:
        db.close()


def create_booking(client, client_headers, artisan_id):
    """Helper to create a booking for testing."""
    from app.core.security import decode_token
    from app.models.booking import Booking, BookingStatus

    db = TestingSessionLocal()
    try:
        token = client_headers["Authorization"].split(" ")[1]
        payload = decode_token(token)
        user_id = int(payload["sub"])

        from app.models.client import Client

        client_profile = db.query(Client).filter(Client.user_id == user_id).first()

        booking = Booking(
            client_id=client_profile.id,
            artisan_id=artisan_id,
            service="Test Service",
            status=BookingStatus.IN_PROGRESS,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return str(booking.id)
    finally:
        db.close()


class TestWebSocketConnection:
    """Tests for WebSocket connection handling."""

    def test_websocket_missing_token(self, client):
        """Test that connection is rejected without a token."""
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/tracking/some-job-id"):
                pass  # Should not reach here

    def test_websocket_invalid_token(self, client):
        """Test that connection is rejected with invalid token."""
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/api/v1/tracking/some-job-id?token=invalid-token"
            ):
                pass


class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def test_connection_manager_connect_disconnect(self):
        """Test connection manager connect and disconnect."""
        from app.api.v1.endpoints.tracking import ConnectionManager

        manager = ConnectionManager()
        websocket = MagicMock()
        websocket.accept = AsyncMock()

        # Test connect
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.connect(websocket, "job-123"))
        finally:
            loop.close()

        assert "job-123" in manager.active_connections
        assert websocket in manager.active_connections["job-123"]

        # Test disconnect
        manager.disconnect(websocket, "job-123")
        assert "job-123" not in manager.active_connections

    def test_connection_manager_cleanup_empty_jobs(self):
        """Test that empty job entries are cleaned up."""
        from app.api.v1.endpoints.tracking import ConnectionManager

        manager = ConnectionManager()
        websocket1 = MagicMock()
        websocket1.accept = AsyncMock()
        websocket2 = MagicMock()
        websocket2.accept = AsyncMock()

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Add two connections to same job
            loop.run_until_complete(manager.connect(websocket1, "job-123"))
            loop.run_until_complete(manager.connect(websocket2, "job-123"))
        finally:
            loop.close()

        assert len(manager.active_connections["job-123"]) == 2

        # Remove one
        manager.disconnect(websocket1, "job-123")
        assert "job-123" in manager.active_connections
        assert len(manager.active_connections["job-123"]) == 1

        # Remove last one - job should be cleaned up
        manager.disconnect(websocket2, "job-123")
        assert "job-123" not in manager.active_connections

    def test_connection_manager_broadcast(self):
        """Test broadcasting messages to connections."""
        from app.api.v1.endpoints.tracking import ConnectionManager

        manager = ConnectionManager()
        websocket1 = MagicMock()
        websocket1.accept = AsyncMock()
        websocket1.send_text = AsyncMock()
        websocket2 = MagicMock()
        websocket2.accept = AsyncMock()
        websocket2.send_text = AsyncMock()

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.connect(websocket1, "job-123"))
            loop.run_until_complete(manager.connect(websocket2, "job-123"))

            # Broadcast message
            message = {"lat": 40.7128, "lng": -74.0060}
            loop.run_until_complete(manager.broadcast("job-123", message))

            # Verify both websockets received the message
            websocket1.send_text.assert_called_once()
            websocket2.send_text.assert_called_once()
        finally:
            loop.close()


class TestTokenVerification:
    """Tests for token verification functions."""

    def test_verify_artisan_token_valid(self, client):
        """Test valid artisan token verification."""
        from app.api.v1.endpoints.tracking import verify_artisan_token

        artisan_headers, artisan_token = get_auth_headers(
            client, "verify_artisan@test.com", "Pass123!", "artisan"
        )
        create_artisan_profile(client, artisan_headers)

        db = TestingSessionLocal()
        try:
            user = verify_artisan_token(artisan_token, db)
            assert user is not None
            assert user.role == "artisan"
        finally:
            db.close()

    def test_verify_artisan_token_client_rejected(self, client):
        """Test that client tokens are rejected for artisan verification."""
        from app.api.v1.endpoints.tracking import verify_artisan_token

        client_headers, client_token = get_auth_headers(
            client, "verify_client@test.com", "Pass123!", "client"
        )

        db = TestingSessionLocal()
        try:
            user = verify_artisan_token(client_token, db)
            assert user is None
        finally:
            db.close()

    def test_verify_client_token_valid(self, client):
        """Test valid client token verification."""
        from app.api.v1.endpoints.tracking import verify_client_token

        client_headers, client_token = get_auth_headers(
            client, "verify_client2@test.com", "Pass123!", "client"
        )

        db = TestingSessionLocal()
        try:
            user = verify_client_token(client_token, db)
            assert user is not None
            assert user.role == "client"
        finally:
            db.close()

    def test_verify_client_token_artisan_rejected(self, client):
        """Test that artisan tokens are rejected for client verification."""
        from app.api.v1.endpoints.tracking import verify_client_token

        artisan_headers, artisan_token = get_auth_headers(
            client, "verify_artisan2@test.com", "Pass123!", "artisan"
        )

        db = TestingSessionLocal()
        try:
            user = verify_client_token(artisan_token, db)
            assert user is None
        finally:
            db.close()
