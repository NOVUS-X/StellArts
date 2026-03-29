"""Unit tests for the run_inventory_check background task."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.inventory.tasks import run_inventory_check


def _make_booking(
    *,
    client_supply_override: bool = False,
    artisan_lat=None,
    artisan_lon=None,
    device_token: str | None = None,
):
    """Build a minimal mock Booking with an attached Artisan."""
    artisan = MagicMock()
    artisan.id = 1
    artisan.latitude = artisan_lat
    artisan.longitude = artisan_lon

    booking = MagicMock()
    booking.id = uuid4()
    booking.client_supply_override = client_supply_override
    booking.artisan = artisan
    booking.artisan_device_token = device_token
    booking.location = None
    return booking


def _make_db(booking=None, bom_items=None):
    """Build a minimal mock Session."""
    db = MagicMock()

    query_mock = MagicMock()
    filter_mock = MagicMock()

    # First query call → Booking; second → BOMItem
    call_count = {"n": 0}

    def query_side_effect(model):
        call_count["n"] += 1
        m = MagicMock()
        m.filter.return_value.first.return_value = booking
        m.filter.return_value.all.return_value = bom_items or []
        return m

    db.query.side_effect = query_side_effect
    return db


# ---------------------------------------------------------------------------
# Test 1: client_supply_override=True skips the inventory check
# ---------------------------------------------------------------------------

def test_client_supply_override_skips_check():
    """When client_supply_override is True, InventoryCheckerService.run_check must not be called."""
    booking = _make_booking(client_supply_override=True)
    db = _make_db(booking=booking)

    with patch(
        "app.services.inventory.tasks.InventoryCheckerService"
    ) as MockChecker:
        asyncio.run(run_inventory_check(booking.id, db))
        MockChecker.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: Missing artisan coordinates skips the check
# ---------------------------------------------------------------------------

def test_missing_artisan_coordinates_skips_check():
    """When artisan has no lat/lon, run_check must not be called."""
    booking = _make_booking(artisan_lat=None, artisan_lon=None)
    bom_items = [MagicMock()]
    db = _make_db(booking=booking, bom_items=bom_items)

    with patch(
        "app.services.inventory.tasks.InventoryCheckerService"
    ) as MockChecker:
        asyncio.run(run_inventory_check(booking.id, db))
        MockChecker.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Empty BOM skips the check
# ---------------------------------------------------------------------------

def test_empty_bom_skips_check():
    """When there are no BOM items, run_check must not be called."""
    booking = _make_booking(artisan_lat=51.5, artisan_lon=-0.1)
    db = _make_db(booking=booking, bom_items=[])

    with patch(
        "app.services.inventory.tasks.InventoryCheckerService"
    ) as MockChecker:
        asyncio.run(run_inventory_check(booking.id, db))
        MockChecker.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: Happy path — run_check is called when all data is present
# ---------------------------------------------------------------------------

def test_happy_path_calls_run_check():
    """When booking has coordinates and BOM items, run_check should be called."""
    booking = _make_booking(artisan_lat=51.5, artisan_lon=-0.1)
    bom_items = [MagicMock()]
    db = _make_db(booking=booking, bom_items=bom_items)

    mock_checker_instance = MagicMock()
    mock_checker_instance.run_check = AsyncMock(return_value=[])

    with patch(
        "app.services.inventory.tasks.InventoryCheckerService",
        return_value=mock_checker_instance,
    ):
        asyncio.run(run_inventory_check(booking.id, db))
        mock_checker_instance.run_check.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5: Exceptions inside the task are swallowed (never raised)
# ---------------------------------------------------------------------------

def test_exceptions_are_swallowed():
    """Unhandled exceptions inside run_inventory_check must not propagate."""
    db = MagicMock()
    db.query.side_effect = RuntimeError("DB exploded")

    # Should not raise
    asyncio.run(run_inventory_check(uuid4(), db))
