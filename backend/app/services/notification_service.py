"""
NotificationService: sends push notifications to artisans when BOM items are
found in stock at stores along their route.

Groups StoreMatch results by store and sends one push notification per store
via FCM (or a compatible Web Push client). Builds Pre_Pay_Link per item from
StockResult.item_url. Includes a staleness warning when inventory data is
older than 1 hour. Schedules a single Celery retry (countdown=60) on delivery
failure; logs and skips retry for invalid device tokens.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.4
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.services.inventory_service import StoreMatch
from app.adapters.store_api_adapter import StockResult

logger = logging.getLogger(__name__)

# Tokens containing any of these strings are considered permanently invalid
# (FCM error codes for unregistered / bad tokens).
_INVALID_TOKEN_MARKERS = (
    "invalid-registration-token",
    "registration-token-not-registered",
)

_STALENESS_THRESHOLD = timedelta(hours=1)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class NotificationResult:
    """
    Outcome of a single push notification attempt for one store.

    Attributes
    ----------
    store_id:
        The store whose items were included in the notification.
    artisan_id:
        The artisan who received (or should have received) the notification.
    status:
        One of ``"sent"``, ``"failed"``, or ``"retried"``.
    notification_count:
        Number of push notifications sent for this store (normally 1).
    """

    store_id: str
    artisan_id: UUID
    status: str          # "sent" | "failed" | "retried"
    notification_count: int


# ---------------------------------------------------------------------------
# NotificationService
# ---------------------------------------------------------------------------


class NotificationService:
    """
    Sends one push notification per store for in-stock BOM items.

    Parameters
    ----------
    fcm_client:
        An object with a ``send(device_token: str, payload: dict) -> dict``
        method.  Pass ``None`` only in unit tests that do not exercise the
        send path; a ``RuntimeError`` is raised if ``send_inventory_alerts``
        is called with ``fcm_client=None``.
    celery_app:
        A Celery application instance used to schedule retry tasks.  May be
        ``None`` in environments where retries are not required (e.g. tests).
    """

    def __init__(self, fcm_client=None, celery_app=None) -> None:
        self._fcm = fcm_client
        self._celery = celery_app

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_inventory_alerts(
        self,
        artisan_id: UUID,
        matches: list[StoreMatch],
        started_at: datetime,
        device_token: str,
    ) -> list[NotificationResult]:
        """
        Send one push notification per store for all in-stock BOM items.

        Each ``StoreMatch`` already represents a single store, so the method
        iterates over ``matches`` directly — one notification per element
        (Requirement 4.6).

        Parameters
        ----------
        artisan_id:
            UUID of the artisan receiving the notifications.
        matches:
            List of ``StoreMatch`` objects, each containing the store details
            and the in-stock ``StockResult`` items found there.
        started_at:
            UTC datetime when the inventory check run began.  Used as the
            reference point for staleness detection (Requirement 5.4).
        device_token:
            The artisan's FCM / Web Push device registration token.

        Returns
        -------
        list[NotificationResult]
            One result per store, indicating whether the notification was
            sent, failed, or scheduled for retry.

        Raises
        ------
        RuntimeError
            When ``fcm_client`` was not provided at construction time.
        """
        if self._fcm is None:
            raise RuntimeError(
                "NotificationService requires an fcm_client to send notifications."
            )

        results: list[NotificationResult] = []

        for match in matches:
            payload = self._build_payload(match, started_at)
            result = await self._send_one(
                artisan_id=artisan_id,
                store_id=match.store_id,
                device_token=device_token,
                payload=payload,
            )
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------

    def _build_payload(self, match: StoreMatch, started_at: datetime) -> dict:
        """
        Build the FCM push notification payload for a single store.

        The body summarises the first item found plus a count of additional
        items.  Each item entry in ``data.items`` includes a ``stale`` flag
        when its ``data_timestamp`` is more than 1 hour before ``started_at``
        (Requirement 5.4).

        Requirements: 4.2, 4.3, 5.4
        """
        items_data = []
        for result in match.results:
            stale = self._is_stale(result, started_at)
            items_data.append(
                {
                    "name": self._item_name(result),
                    "pre_pay_url": result.item_url,
                    "stale": stale,
                }
            )

        # Body: "Found {first_item} + {N} others at {store_name}"
        first_name = items_data[0]["name"] if items_data else "items"
        others = len(items_data) - 1
        if others > 0:
            body = f"Found {first_name} + {others} others at {match.store_name}"
        else:
            body = f"Found {first_name} at {match.store_name}"

        return {
            "title": "Parts available on your route",
            "body": body,
            "data": {
                "store_id": match.store_id,
                "store_name": match.store_name,
                "store_address": match.store_address,
                "items": items_data,
            },
        }

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    async def _send_one(
        self,
        artisan_id: UUID,
        store_id: str,
        device_token: str,
        payload: dict,
    ) -> NotificationResult:
        """
        Attempt to deliver a single push notification.

        On success returns a ``NotificationResult`` with ``status="sent"``.

        On failure:
        - If the error indicates an invalid/unregistered device token, logs
          the failure and returns ``status="failed"`` without scheduling a
          retry (Requirement 4.5).
        - Otherwise, schedules a single Celery retry after 60 seconds and
          returns ``status="retried"`` (Requirement 4.5).

        Requirements: 4.1, 4.5
        """
        try:
            response = self._fcm.send(device_token, payload)
            logger.info(
                "Push notification sent to artisan %s for store %s (response: %s)",
                artisan_id,
                store_id,
                response,
            )
            return NotificationResult(
                store_id=store_id,
                artisan_id=artisan_id,
                status="sent",
                notification_count=1,
            )

        except Exception as exc:  # noqa: BLE001
            error_str = str(exc).lower()

            if any(marker in error_str for marker in _INVALID_TOKEN_MARKERS):
                logger.warning(
                    "Invalid device token for artisan %s (store %s): %s — skipping retry",
                    artisan_id,
                    store_id,
                    exc,
                )
                return NotificationResult(
                    store_id=store_id,
                    artisan_id=artisan_id,
                    status="failed",
                    notification_count=0,
                )

            # Transient failure — schedule a single retry via Celery
            logger.error(
                "Push notification failed for artisan %s (store %s): %s — scheduling retry",
                artisan_id,
                store_id,
                exc,
            )
            self._schedule_retry(
                artisan_id=artisan_id,
                store_id=store_id,
                device_token=device_token,
                payload=payload,
            )
            return NotificationResult(
                store_id=store_id,
                artisan_id=artisan_id,
                status="retried",
                notification_count=0,
            )

    def _schedule_retry(
        self,
        artisan_id: UUID,
        store_id: str,
        device_token: str,
        payload: dict,
    ) -> None:
        """
        Enqueue a single retry notification task via Celery with a 60-second
        countdown (Requirement 4.5).

        If no Celery app is configured, logs a warning and skips scheduling.
        """
        if self._celery is None:
            logger.warning(
                "No Celery app configured — cannot schedule retry for artisan %s store %s",
                artisan_id,
                store_id,
            )
            return

        self._celery.send_task(
            "retry_notification",
            kwargs={
                "artisan_id": str(artisan_id),
                "store_id": store_id,
                "device_token": device_token,
                "payload": payload,
            },
            countdown=60,
        )
        logger.info(
            "Retry notification scheduled (countdown=60s) for artisan %s store %s",
            artisan_id,
            store_id,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_stale(result: StockResult, started_at: datetime) -> bool:
        """
        Return True when the stock result's data is more than 1 hour older
        than the check run's start time (Requirement 5.4).

        Both datetimes are normalised to UTC-aware before comparison to avoid
        naive/aware mixing errors.
        """
        ts = result.data_timestamp
        ref = started_at

        # Ensure both are timezone-aware (assume UTC if naive)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        return (ref - ts) > _STALENESS_THRESHOLD

    @staticmethod
    def _item_name(result: StockResult) -> str:
        """
        Extract a human-readable item name from a StockResult.

        StockResult does not carry a ``part_name`` field directly; the item
        URL is the canonical identifier available on the result.  Callers
        that need a display name should enrich the StoreMatch before passing
        it to NotificationService, or subclass and override this method.

        For now, derive a best-effort name from the URL path's last segment.
        """
        url = result.item_url or ""
        # Strip query string and trailing slash, then take the last path segment
        path = url.split("?")[0].rstrip("/")
        segment = path.split("/")[-1] if "/" in path else path
        return segment or "item"


# ---------------------------------------------------------------------------
# Module-level compatibility shim
# ---------------------------------------------------------------------------
# booking.py calls `notification_service.dispatch_to_matched_artisans(db, booking)`
# as a fire-and-forget async call.  This stub preserves that interface so
# existing booking tests continue to pass while the full push-notification
# pipeline is wired up in later tasks.


async def dispatch_to_matched_artisans(db, booking) -> None:
    """
    Dispatch smart-pitch notifications to artisans matched to a new booking.

    This is a compatibility shim used by the booking endpoint.  The full
    implementation will be added when the artisan-matching notification
    pipeline is wired up.  For now it is a no-op so that booking creation
    does not fail when no FCM client is configured.
    """
    logger.debug(
        "dispatch_to_matched_artisans called for booking %s (no-op stub)",
        getattr(booking, "id", booking),
    )
