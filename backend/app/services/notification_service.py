"""NotificationService — sends FCM push notifications for inventory alerts."""
from __future__ import annotations

import logging
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory import InventoryCheckResult
from app.models.notification import NotificationEvent

logger = logging.getLogger(__name__)

FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"


def _get_bearer_token() -> str | None:
    """Obtain a short-lived OAuth2 bearer token from the FCM service account JSON."""
    if not settings.FCM_SERVICE_ACCOUNT_JSON:
        return None
    try:
        import json

        import google.auth.transport.requests
        import google.oauth2.service_account

        info = json.loads(settings.FCM_SERVICE_ACCOUNT_JSON)
        credentials = google.oauth2.service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        return credentials.token
    except Exception as exc:
        logger.warning("Failed to obtain FCM bearer token: %s", exc)
        return None


class NotificationService:
    async def send_inventory_alert(
        self,
        artisan_device_token: str,
        item_name: str,
        store_name: str,
        store_id: str,
        pre_pay_url: str,
        booking_id: UUID,
        db: Session,
        artisan_id: int | None = None,
    ) -> bool:
        """Send a single FCM push notification and persist a NotificationEvent row.

        Returns True if FCM accepted the message, False otherwise.
        """
        payload = {
            "message": {
                "token": artisan_device_token,
                "notification": {
                    "title": f"Item available: {item_name}",
                    "body": f"{item_name} is in stock at {store_name}",
                },
                "data": {
                    "item_name": item_name,
                    "store_name": store_name,
                    "store_id": store_id,
                    "pre_pay_url": pre_pay_url,
                    "booking_id": str(booking_id),
                },
            }
        }

        fcm_success = False

        if settings.FCM_PROJECT_ID is None:
            logger.warning("FCM_PROJECT_ID not configured — skipping FCM call")
        else:
            token = _get_bearer_token()
            url = FCM_SEND_URL.format(project_id=settings.FCM_PROJECT_ID)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 404:
                    logger.warning(
                        "FCM device token not found (404) for booking=%s store=%s",
                        booking_id,
                        store_id,
                    )
                elif response.status_code >= 400:
                    logger.error(
                        "FCM error %s for booking=%s store=%s: %s",
                        response.status_code,
                        booking_id,
                        store_id,
                        response.text,
                    )
                else:
                    fcm_success = True
            except Exception as exc:
                logger.error("FCM request failed for booking=%s: %s", booking_id, exc)

        # Always persist the notification event
        event = NotificationEvent(
            artisan_id=artisan_id or 0,
            booking_id=booking_id,
            store_id=store_id,
            item_sku=item_name,  # use item_name as sku proxy when no sku provided
            fcm_success=fcm_success,
        )
        db.add(event)
        db.flush()

        return fcm_success

    async def send_batch(
        self,
        artisan_device_token: str,
        results: list[InventoryCheckResult],
        booking_id: UUID,
        db: Session,
        artisan_id: int | None = None,
    ) -> int:
        """Send up to 5 notifications for available inventory results.

        Returns the number of notifications sent.
        """
        available = [r for r in results if r.available]
        capped = available[:5]

        count = 0
        for result in capped:
            await self.send_inventory_alert(
                artisan_device_token=artisan_device_token,
                item_name=result.store_name,  # store_name as item proxy; callers may override
                store_name=result.store_name,
                store_id=result.store_id,
                pre_pay_url=result.pre_pay_url or "",
                booking_id=booking_id,
                db=db,
                artisan_id=artisan_id,
            )
            count += 1

        return count


notification_service = NotificationService()
