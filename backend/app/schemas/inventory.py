from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BOMItemCreate(BaseModel):
    sku: str
    name: str
    quantity: int = Field(ge=1)
    unit: str | None = None


class BOMItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: UUID
    sku: str
    name: str
    quantity: int
    unit: str | None
    created_at: datetime


class InventoryCheckResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: UUID
    bom_item_id: int
    store_id: str
    store_name: str
    store_address: str | None
    available: bool
    pre_pay_url: str | None
    status: str  # "fresh" | "stale" | "unavailable"
    checked_at: datetime


class ClientSupplyOverrideRequest(BaseModel):
    client_supply_override: bool
