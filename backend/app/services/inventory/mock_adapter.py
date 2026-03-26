from __future__ import annotations

import asyncio

from .base import StoreItemResult


class MockStoreAdapter:
    """In-memory store adapter for use in tests."""

    def __init__(
        self,
        store_id: str,
        store_name: str,
        store_lat: float,
        store_lon: float,
        items: dict[str, StoreItemResult] | None = None,
        should_raise: Exception | None = None,
        should_timeout: bool = False,
    ) -> None:
        self.store_id = store_id
        self.store_name = store_name
        self.store_lat = store_lat
        self.store_lon = store_lon
        self._items: dict[str, StoreItemResult] = items or {}
        self._should_raise = should_raise
        self._should_timeout = should_timeout

    async def query_item(self, sku: str, quantity: int) -> StoreItemResult:
        if self._should_raise is not None:
            raise self._should_raise

        if self._should_timeout:
            # Sleep longer than any realistic timeout to simulate a hung request
            await asyncio.sleep(3600)

        if sku in self._items:
            return self._items[sku]

        return StoreItemResult(sku=sku, available=False)
