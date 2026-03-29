"""Unit tests for inventory Pydantic schemas — serialisation round-trip.

Validates: Requirements 4.1
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.schemas.inventory import (
    BOMItemCreate,
    BOMItemResponse,
    ClientSupplyOverrideRequest,
    InventoryCheckResultResponse,
)


def _sample_result_data() -> dict:
    return {
        "id": 1,
        "booking_id": uuid4(),
        "bom_item_id": 2,
        "store_id": "store-abc",
        "store_name": "Test Store",
        "store_address": "1 High Street",
        "available": True,
        "pre_pay_url": "https://example.com/pay",
        "status": "fresh",
        "checked_at": datetime.now(timezone.utc),
    }


def test_inventory_check_result_round_trip():
    """InventoryCheckResultResponse serialises and deserialises without data loss."""
    data = _sample_result_data()
    obj = InventoryCheckResultResponse(**data)
    dumped = obj.model_dump()
    restored = InventoryCheckResultResponse(**dumped)

    assert restored.id == obj.id
    assert restored.booking_id == obj.booking_id
    assert restored.bom_item_id == obj.bom_item_id
    assert restored.store_id == obj.store_id
    assert restored.store_name == obj.store_name
    assert restored.store_address == obj.store_address
    assert restored.available == obj.available
    assert restored.pre_pay_url == obj.pre_pay_url
    assert restored.status == obj.status
    assert restored.checked_at == obj.checked_at


def test_inventory_check_result_nullable_fields():
    """Optional fields accept None without error."""
    data = _sample_result_data()
    data["store_address"] = None
    data["pre_pay_url"] = None
    obj = InventoryCheckResultResponse(**data)
    assert obj.store_address is None
    assert obj.pre_pay_url is None


def test_bom_item_create_validation():
    """BOMItemCreate rejects quantity < 1."""
    import pytest
    with pytest.raises(Exception):
        BOMItemCreate(sku="X", name="Widget", quantity=0)


def test_bom_item_response_round_trip():
    """BOMItemResponse serialises and deserialises without data loss."""
    data = {
        "id": 5,
        "booking_id": uuid4(),
        "sku": "SKU-001",
        "name": "Pipe",
        "quantity": 3,
        "unit": "m",
        "created_at": datetime.now(timezone.utc),
    }
    obj = BOMItemResponse(**data)
    restored = BOMItemResponse(**obj.model_dump())
    assert restored == obj


def test_client_supply_override_request():
    """ClientSupplyOverrideRequest accepts bool values."""
    assert ClientSupplyOverrideRequest(client_supply_override=True).client_supply_override is True
    assert ClientSupplyOverrideRequest(client_supply_override=False).client_supply_override is False
