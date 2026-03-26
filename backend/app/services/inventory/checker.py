from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bom import BOMItem
from app.models.inventory import InventoryCheckResult
from app.services.route_service import RouteCorridorResult, route_service

from .base import StoreAdapterProtocol, StoreItemResult

logger = logging.getLogger(__name__)

_CACHE_KEY = "inv:{store_id}:{sku}"


def _serialise(result: StoreItemResult) -> str:
    return json.dumps(
        {
            "sku": result.sku,
            "available": result.available,
            "quantity_on_hand": result.quantity_on_hand,
            "unit_price": result.unit_price,
            "pre_pay_url": result.pre_pay_url,
            "error": result.error,
        }
    )


def _deserialise(raw: str) -> StoreItemResult:
    data = json.loads(raw)
    return StoreItemResult(
        sku=data["sku"],
        available=data["available"],
        quantity_on_hand=data.get("quantity_on_hand"),
        unit_price=data.get("unit_price"),
        pre_pay_url=data.get("pre_pay_url"),
        error=data.get("error"),
    )


class InventoryCheckerService:
    def __init__(
        self,
        adapters: list[StoreAdapterProtocol],
        cache=None,  # Redis client or None
    ) -> None:
        self._adapters = adapters
        self._cache = cache

    async def run_check(
        self,
        booking_id: UUID,
        bom_items: list[BOMItem],
        corridor: RouteCorridorResult,
        db: Session,
    ) -> list[InventoryCheckResult]:
        # Filter adapters to those within the corridor
        in_corridor = [
            a for a in self._adapters
            if route_service.point_in_corridor(a.store_lat, a.store_lon, corridor)
        ]

        results: list[InventoryCheckResult] = []

        for adapter in in_corridor:
            for item in bom_items:
                cache_key = _CACHE_KEY.format(store_id=adapter.store_id, sku=item.sku)
                item_result: StoreItemResult | None = None

                # Try cache first
                if self._cache is not None:
                    try:
                        cached = await self._cache.get(cache_key)
                        if cached is not None:
                            item_result = _deserialise(cached)
                    except Exception as exc:
                        logger.warning("Redis get failed for %s: %s", cache_key, exc)

                # Cache miss — call live adapter
                if item_result is None:
                    try:
                        item_result = await asyncio.wait_for(
                            adapter.query_item(item.sku, item.quantity),
                            timeout=settings.STORE_API_TIMEOUT_S,
                        )
                        # Cache the successful result
                        if self._cache is not None:
                            try:
                                await self._cache.set(
                                    cache_key,
                                    _serialise(item_result),
                                    ex=settings.INVENTORY_CACHE_TTL,
                                )
                            except Exception as exc:
                                logger.warning(
                                    "Redis set failed for %s: %s", cache_key, exc
                                )
                    except Exception as exc:
                        logger.error(
                            "Adapter %s failed for sku=%s: %s",
                            adapter.store_id,
                            item.sku,
                            exc,
                        )
                        row = InventoryCheckResult(
                            booking_id=booking_id,
                            bom_item_id=item.id,
                            store_id=adapter.store_id,
                            store_name=adapter.store_name,
                            store_address=getattr(adapter, "store_address", None),
                            available=False,
                            status="unavailable",
                        )
                        db.add(row)
                        results.append(row)
                        continue

                row = InventoryCheckResult(
                    booking_id=booking_id,
                    bom_item_id=item.id,
                    store_id=adapter.store_id,
                    store_name=adapter.store_name,
                    store_address=getattr(adapter, "store_address", None),
                    available=item_result.available,
                    pre_pay_url=item_result.pre_pay_url,
                    status="fresh",
                )
                db.add(row)
                results.append(row)

        db.flush()
        return results
