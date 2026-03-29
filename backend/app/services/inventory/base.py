from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class StoreItemResult:
    sku: str
    available: bool
    quantity_on_hand: int | None = None
    unit_price: float | None = None
    pre_pay_url: str | None = None
    error: str | None = None


class StoreAdapterProtocol(Protocol):
    store_id: str
    store_name: str
    store_lat: float
    store_lon: float

    async def query_item(self, sku: str, quantity: int) -> StoreItemResult: ...
