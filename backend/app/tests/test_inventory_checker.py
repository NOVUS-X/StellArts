"""Unit tests for InventoryCheckerService."""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.bom import BOMItem
from app.services.inventory.base import StoreItemResult
from app.services.inventory.checker import InventoryCheckerService, _deserialise, _serialise
from app.services.inventory.mock_adapter import MockStoreAdapter
from app.services.route_service import RouteService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_corridor(
    origin=(40.0, -74.0),
    dest=(40.1, -74.1),
    half_width_m=50_000.0,
):
    rs = RouteService()
    return rs.compute_corridor(*origin, *dest, half_width_m=half_width_m)


def make_bom_item(sku="SKU-001", quantity=1, item_id=1):
    item = MagicMock(spec=BOMItem)
    item.id = item_id
    item.sku = sku
    item.quantity = quantity
    return item


def make_db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Corridor filtering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapter_outside_corridor_is_skipped():
    """Adapters whose location falls outside the corridor must not be queried."""
    corridor = make_corridor(origin=(40.0, -74.0), dest=(40.1, -74.1), half_width_m=500.0)

    inside = MockStoreAdapter(
        store_id="inside",
        store_name="Inside Store",
        store_lat=40.05,
        store_lon=-74.05,
        items={"SKU-001": StoreItemResult(sku="SKU-001", available=True)},
    )
    outside = MockStoreAdapter(
        store_id="outside",
        store_name="Outside Store",
        store_lat=99.0,  # far away
        store_lon=99.0,
        items={"SKU-001": StoreItemResult(sku="SKU-001", available=True)},
    )

    svc = InventoryCheckerService(adapters=[inside, outside], cache=None)
    bom = [make_bom_item()]
    db = make_db()

    results = await svc.run_check(uuid.uuid4(), bom, corridor, db)

    store_ids = {r.store_id for r in results}
    assert "inside" in store_ids
    assert "outside" not in store_ids


@pytest.mark.asyncio
async def test_no_adapters_in_corridor_returns_empty():
    corridor = make_corridor(origin=(40.0, -74.0), dest=(40.1, -74.1), half_width_m=500.0)
    adapter = MockStoreAdapter(
        store_id="far",
        store_name="Far Store",
        store_lat=99.0,
        store_lon=99.0,
    )
    svc = InventoryCheckerService(adapters=[adapter], cache=None)
    results = await svc.run_check(uuid.uuid4(), [make_bom_item()], corridor, make_db())
    assert results == []


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_skips_adapter_call():
    """When Redis returns a cached value, adapter.query_item must not be called."""
    corridor = make_corridor(half_width_m=50_000.0)

    adapter = MockStoreAdapter(
        store_id="s1",
        store_name="Store 1",
        store_lat=40.05,
        store_lon=-74.05,
    )
    # Spy on query_item
    adapter.query_item = AsyncMock(return_value=StoreItemResult(sku="SKU-001", available=True))

    cached_result = StoreItemResult(sku="SKU-001", available=True, pre_pay_url="http://pay")
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=_serialise(cached_result))
    cache.set = AsyncMock()

    svc = InventoryCheckerService(adapters=[adapter], cache=cache)
    bom = [make_bom_item()]
    results = await svc.run_check(uuid.uuid4(), bom, corridor, make_db())

    adapter.query_item.assert_not_called()
    assert len(results) == 1
    assert results[0].available is True


@pytest.mark.asyncio
async def test_cache_miss_calls_adapter_and_stores_result():
    """On a cache miss the adapter is called and the result is stored in Redis."""
    corridor = make_corridor(half_width_m=50_000.0)

    adapter = MockStoreAdapter(
        store_id="s1",
        store_name="Store 1",
        store_lat=40.05,
        store_lon=-74.05,
        items={"SKU-001": StoreItemResult(sku="SKU-001", available=True)},
    )

    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)  # cache miss
    cache.set = AsyncMock()

    svc = InventoryCheckerService(adapters=[adapter], cache=cache)
    bom = [make_bom_item()]
    results = await svc.run_check(uuid.uuid4(), bom, corridor, make_db())

    cache.set.assert_called_once()
    assert results[0].available is True


# ---------------------------------------------------------------------------
# Error isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failing_adapter_does_not_prevent_others():
    """An exception from one adapter must not stop other adapters from being queried."""
    corridor = make_corridor(half_width_m=50_000.0)

    failing = MockStoreAdapter(
        store_id="fail",
        store_name="Failing Store",
        store_lat=40.05,
        store_lon=-74.05,
        should_raise=RuntimeError("boom"),
    )
    ok = MockStoreAdapter(
        store_id="ok",
        store_name="OK Store",
        store_lat=40.05,
        store_lon=-74.05,
        items={"SKU-001": StoreItemResult(sku="SKU-001", available=True)},
    )

    svc = InventoryCheckerService(adapters=[failing, ok], cache=None)
    bom = [make_bom_item()]
    results = await svc.run_check(uuid.uuid4(), bom, corridor, make_db())

    store_ids = {r.store_id for r in results}
    assert "fail" in store_ids
    assert "ok" in store_ids

    fail_result = next(r for r in results if r.store_id == "fail")
    ok_result = next(r for r in results if r.store_id == "ok")

    assert fail_result.status == "unavailable"
    assert fail_result.available is False
    assert ok_result.available is True


@pytest.mark.asyncio
async def test_timeout_marks_result_unavailable():
    """A timed-out adapter call must produce an unavailable result."""
    corridor = make_corridor(half_width_m=50_000.0)

    adapter = MockStoreAdapter(
        store_id="slow",
        store_name="Slow Store",
        store_lat=40.05,
        store_lon=-74.05,
        should_timeout=True,
    )

    svc = InventoryCheckerService(adapters=[adapter], cache=None)
    bom = [make_bom_item()]

    with patch("app.services.inventory.checker.settings") as mock_settings:
        mock_settings.STORE_API_TIMEOUT_S = 0.01  # very short timeout
        mock_settings.INVENTORY_CACHE_TTL = 300
        results = await svc.run_check(uuid.uuid4(), bom, corridor, make_db())

    assert len(results) == 1
    assert results[0].status == "unavailable"
    assert results[0].available is False


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def test_serialise_deserialise_roundtrip():
    original = StoreItemResult(
        sku="ABC-123",
        available=True,
        quantity_on_hand=5,
        unit_price=9.99,
        pre_pay_url="http://example.com/pay",
        error=None,
    )
    assert _deserialise(_serialise(original)) == original


def test_serialise_deserialise_with_none_fields():
    original = StoreItemResult(sku="X", available=False)
    assert _deserialise(_serialise(original)) == original
