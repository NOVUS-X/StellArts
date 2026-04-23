"""
HomeDepotAdapter: concrete StoreAPIAdapter for the Home Depot inventory API.

Normalises the Home Depot HTTP JSON response into common StockResult objects.
Enforces a 5-second timeout on all HTTP calls per Requirement 2.4.

Requirements: 2.2, 2.4
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import aiohttp

from app.adapters.store_api_adapter import StockResult, StoreAPIAdapter

# Expected external API response shape:
# {
#   "items": [
#     {
#       "part_number": "SKU-123",
#       "in_stock": true,
#       "quantity": 5,
#       "product_url": "https://homedepot.com/p/SKU-123",
#       "last_updated": "2024-01-01T12:00:00Z"
#     }
#   ]
# }

_TIMEOUT = aiohttp.ClientTimeout(total=5)


class HomeDepotAdapter(StoreAPIAdapter):
    """
    Inventory adapter for Home Depot store locations.

    Parameters
    ----------
    api_config:
        Adapter-specific configuration dict stored in ``stores.api_config``.
        Expected keys:
          - ``base_url`` (str): Root URL of the Home Depot inventory API.
          - ``api_key`` (str): Bearer token / API key for authentication.
    """

    def __init__(self, api_config: dict) -> None:
        self._base_url: str = api_config["base_url"].rstrip("/")
        self._api_key: str = api_config.get("api_key", "")

    async def check_stock(
        self,
        store_id: str,
        bom_items: list,
    ) -> list[StockResult]:
        """
        Query the Home Depot inventory API for a list of BOM items at a
        specific store location and return normalised StockResult objects.

        The HTTP call is subject to a hard 5-second timeout
        (``aiohttp.ClientTimeout(total=5)``).  If the call times out or
        raises a network error, the exception propagates to the caller
        (InventoryService) which marks the store as unavailable and
        continues processing remaining stores (Requirement 2.4).

        Parameters
        ----------
        store_id:
            Identifier of the specific Home Depot store to query.
        bom_items:
            BOM line items to check.  Each item must expose
            ``bom_item_id`` (UUID) and ``part_number`` (str).

        Returns
        -------
        list[StockResult]
            One StockResult per BOM item.  Items not found in the API
            response are returned as out-of-stock with an empty URL and
            the current UTC time as ``data_timestamp``.
        """
        if not bom_items:
            return []

        part_numbers = [item.part_number for item in bom_items]
        url = f"{self._base_url}/stores/{store_id}/inventory"
        headers = self._build_headers()
        payload = {"part_numbers": part_numbers}

        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()
                data: dict[str, Any] = await response.json()

        return self._normalise(store_id, bom_items, data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _normalise(
        self,
        store_id: str,
        bom_items: list,
        api_response: dict[str, Any],
    ) -> list[StockResult]:
        """
        Map the raw API response onto StockResult objects.

        Items present in the response are matched by ``part_number``.
        BOM items with no matching entry in the response are treated as
        not stocked (``in_stock=False``, ``quantity_available=0``).
        """
        # Build a lookup from part_number → raw item dict
        response_by_part: dict[str, dict] = {
            item["part_number"]: item
            for item in api_response.get("items", [])
        }

        now_utc = datetime.now(tz=timezone.utc)
        results: list[StockResult] = []

        for bom_item in bom_items:
            raw = response_by_part.get(bom_item.part_number)

            if raw is None:
                # Store does not carry this part
                results.append(
                    StockResult(
                        bom_item_id=bom_item.bom_item_id,
                        store_id=store_id,
                        in_stock=False,
                        quantity_available=0,
                        item_url="",
                        data_timestamp=now_utc,
                    )
                )
                continue

            data_timestamp = _parse_timestamp(raw.get("last_updated"), fallback=now_utc)

            results.append(
                StockResult(
                    bom_item_id=bom_item.bom_item_id,
                    store_id=store_id,
                    in_stock=bool(raw.get("in_stock", False)),
                    quantity_available=int(raw.get("quantity", 0)),
                    item_url=raw.get("product_url", ""),
                    data_timestamp=data_timestamp,
                )
            )

        return results


def _parse_timestamp(value: str | None, *, fallback: datetime) -> datetime:
    """
    Parse an ISO-8601 UTC timestamp string from the API response.

    Returns *fallback* when the value is absent or cannot be parsed.
    """
    if not value:
        return fallback
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Ensure the result is timezone-aware UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return fallback
