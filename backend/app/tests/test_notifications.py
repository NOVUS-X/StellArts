from unittest.mock import patch

from app.db.session import get_db
from app.main import app
from app.models.notification import Notification


def get_authenticated_client_and_user(client):
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "notification_user@example.com",
            "password": "StrongPass1!",
            "role": "client",
            "full_name": "Notification User",
        },
    )
    assert register_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "notification_user@example.com",
            "password": "StrongPass1!",
        },
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, token, register_resp.json()["id"]


def test_get_empty_notifications(client):
    with patch("app.core.auth.is_token_blacklisted", return_value=False):
        headers, _, _ = get_authenticated_client_and_user(client)
        response = client.get("/api/v1/notifications/", headers=headers)
        assert response.status_code == 200
        assert response.json() == []


def test_get_unread_count(client):
    with patch("app.core.auth.is_token_blacklisted", return_value=False):
        headers, _, user_id = get_authenticated_client_and_user(client)

        db = next(app.dependency_overrides[get_db]())
        try:
            n1 = Notification(
                user_id=user_id,
                type="booking_confirmed",
                title="Test Notification 1",
                message="Message 1",
                is_read=False,
            )
            n2 = Notification(
                user_id=user_id,
                type="payment_released",
                title="Test Notification 2",
                message="Message 2",
                is_read=True,
            )
            db.add_all([n1, n2])
            db.commit()
        finally:
            db.close()

        response = client.get("/api/v1/notifications/unread-count", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"unread_count": 1}


def test_mark_as_read(client):
    with patch("app.core.auth.is_token_blacklisted", return_value=False):
        headers, _, user_id = get_authenticated_client_and_user(client)

        db = next(app.dependency_overrides[get_db]())
        try:
            notification = Notification(
                user_id=user_id,
                type="bid_received",
                title="New Bid",
                message="You have a new bid",
                is_read=False,
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
            n_id = str(notification.id)
        finally:
            db.close()

        response = client.put(
            f"/api/v1/notifications/{n_id}/read",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_read"] is True


def test_mark_all_as_read(client):
    with patch("app.core.auth.is_token_blacklisted", return_value=False):
        headers, _, user_id = get_authenticated_client_and_user(client)

        db = next(app.dependency_overrides[get_db]())
        try:
            n1 = Notification(
                user_id=user_id,
                type="type1",
                title="Title 1",
                message="Message 1",
                is_read=False,
            )
            n2 = Notification(
                user_id=user_id,
                type="type2",
                title="Title 2",
                message="Message 2",
                is_read=False,
            )
            db.add_all([n1, n2])
            db.commit()
        finally:
            db.close()

        response = client.put(
            "/api/v1/notifications/mark-all-read",
            headers=headers,
        )
        assert response.status_code == 200

        unread_res = client.get("/api/v1/notifications/unread-count", headers=headers)
        assert unread_res.json() == {"unread_count": 0}


def test_delete_notification(client):
    with patch("app.core.auth.is_token_blacklisted", return_value=False):
        headers, _, user_id = get_authenticated_client_and_user(client)

        db = next(app.dependency_overrides[get_db]())
        try:
            notification = Notification(
                user_id=user_id,
                type="type1",
                title="Delete Me",
                message="Message to delete",
                is_read=False,
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
            n_id = str(notification.id)
        finally:
            db.close()

        response = client.delete(
            f"/api/v1/notifications/{n_id}",
            headers=headers,
        )
        assert response.status_code == 200


def test_websocket_stream_connection(client):
    with patch(
        "app.api.v1.endpoints.notifications.is_token_blacklisted", return_value=False
    ):
        _, token, _ = get_authenticated_client_and_user(client)
        with client.websocket_connect(
            f"/api/v1/notifications/stream?token={token}"
        ) as websocket:
            assert websocket is not None
