"""Unit tests for NotificationService."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.inventory import InventoryCheckResult
from app.services.notification_service import NotificationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    return db


def make_result(store_id: str, available: bool = True, pre_pay_url: str = "http://pay") -> InventoryCheckResult:
    r = MagicMock(spec=InventoryCheckResult)
    r.store_id = store_id
    r.store_name = f"Store {store_id}"
    r.available = available
    r.pre_pay_url = pre_pay_url
    return r


# ---------------------------------------------------------------------------
# send_batch caps at 5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_batch_caps_at_five():
    """send_batch must send at most 5 notifications regardless of input size."""
    svc = NotificationService()
    results = [make_result(str(i)) for i in range(10)]
    booking_id = uuid.uuid4()
    db = make_db()

    with patch.object(svc, "send_inventory_alert", new_callable=AsyncMock, return_value=True) as mock_alert:
        count = await svc.send_batch("token", results, booking_id, db)

    assert count == 5
    assert mock_alert.call_count == 5


@pytest.mark.asyncio
async def test_send_batch_skips_unavailable():
    """send_batch must only notify for available=True results."""
    svc = NotificationService()
    results = [
        make_result("a", available=True),
        make_result("b", available=False),
        make_result("c", available=True),
    ]
    booking_id = uuid.uuid4()
    db = make_db()

    with patch.object(svc, "send_inventory_alert", new_callable=AsyncMock, return_value=True) as mock_alert:
        count = await svc.send_batch("token", results, booking_id, db)

    assert count == 2
    assert mock_alert.call_count == 2


# ---------------------------------------------------------------------------
# FCM payload contains required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fcm_payload_contains_required_fields():
    """FCM payload must include item_name, store_name, store_id, pre_pay_url, booking_id."""
    svc = NotificationService()
    booking_id = uuid.uuid4()
    db = make_db()

    captured_payload = {}

    async def fake_post(url, json, headers):
        captured_payload.update(json)
        resp = MagicMock()
        resp.status_code = 200
        return resp

    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.FCM_PROJECT_ID = "test-project"
        mock_settings.FCM_SERVICE_ACCOUNT_JSON = None

        with patch("app.services.notification_service._get_bearer_token", return_value="tok"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(side_effect=fake_post)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await svc.send_inventory_alert(
                    artisan_device_token="device-token",
                    item_name="Hammer",
                    store_name="Tool Shop",
                    store_id="store-42",
                    pre_pay_url="http://pay/123",
                    booking_id=booking_id,
                    db=db,
                )

    data = captured_payload["message"]["data"]
    assert data["item_name"] == "Hammer"
    assert data["store_name"] == "Tool Shop"
    assert data["store_id"] == "store-42"
    assert data["pre_pay_url"] == "http://pay/123"
    assert data["booking_id"] == str(booking_id)


# ---------------------------------------------------------------------------
# FCM 404 does not raise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fcm_404_does_not_raise():
    """A 404 from FCM must not raise an exception; fcm_success must be False."""
    svc = NotificationService()
    booking_id = uuid.uuid4()
    db = make_db()

    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.FCM_PROJECT_ID = "test-project"
        mock_settings.FCM_SERVICE_ACCOUNT_JSON = None

        with patch("app.services.notification_service._get_bearer_token", return_value="tok"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                resp = MagicMock()
                resp.status_code = 404
                mock_client.post = AsyncMock(return_value=resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await svc.send_inventory_alert(
                    artisan_device_token="bad-token",
                    item_name="Nail",
                    store_name="Hardware",
                    store_id="s1",
                    pre_pay_url="http://pay",
                    booking_id=booking_id,
                    db=db,
                )

    assert result is False


# ---------------------------------------------------------------------------
# NotificationEvent row is persisted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_event_persisted_on_success():
    """A NotificationEvent row must be added to the DB on FCM success."""
    svc = NotificationService()
    booking_id = uuid.uuid4()
    db = make_db()

    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.FCM_PROJECT_ID = "test-project"
        mock_settings.FCM_SERVICE_ACCOUNT_JSON = None

        with patch("app.services.notification_service._get_bearer_token", return_value="tok"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                resp = MagicMock()
                resp.status_code = 200
                mock_client.post = AsyncMock(return_value=resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await svc.send_inventory_alert(
                    artisan_device_token="token",
                    item_name="Bolt",
                    store_name="Depot",
                    store_id="s2",
                    pre_pay_url="http://pay",
                    booking_id=booking_id,
                    db=db,
                )

    db.add.assert_called_once()
    db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_notification_event_persisted_on_fcm_failure():
    """A NotificationEvent row must be added even when FCM returns an error."""
    svc = NotificationService()
    booking_id = uuid.uuid4()
    db = make_db()

    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.FCM_PROJECT_ID = "test-project"
        mock_settings.FCM_SERVICE_ACCOUNT_JSON = None

        with patch("app.services.notification_service._get_bearer_token", return_value="tok"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                resp = MagicMock()
                resp.status_code = 500
                resp.text = "internal error"
                mock_client.post = AsyncMock(return_value=resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await svc.send_inventory_alert(
                    artisan_device_token="token",
                    item_name="Screw",
                    store_name="Depot",
                    store_id="s3",
                    pre_pay_url="http://pay",
                    booking_id=booking_id,
                    db=db,
                )

    assert result is False
    db.add.assert_called_once()
    db.flush.assert_called_once()
