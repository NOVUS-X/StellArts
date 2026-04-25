"""
StoreAPIAdapter: abstract base class for hardware store inventory adapters.

Each concrete adapter normalises a store chain's external HTTP API response
into a common StockResult, allowing InventoryService to work with any store
without knowing the details of its API.

Requirements: 2.2, 2.3, 5.4
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class StockResult:
    """
    Normalised inventory result for a single BOM item at a single store.

    Attributes
    ----------
    bom_item_id:
        The UUID of the BOM line item that was queried.
    store_id:
        The store's identifier (matches ``stores.id`` in the database).
    in_stock:
        True when the item is available for purchase at this store.
    quantity_available:
        Number of units currently on hand (0 when ``in_stock`` is False).
    item_url:
        Direct URL to the item on the store's website; used to build the
        Pre_Pay_Link embedded in push notifications.
    data_timestamp:
        UTC datetime at which the store's inventory system last updated this
        record.  Used by NotificationService to detect stale data (> 1 hour
        old) and include a staleness warning in the push notification payload.
        Requirement 5.4.
    """

    bom_item_id: UUID
    store_id: str
    in_stock: bool
    quantity_available: int
    item_url: str
    data_timestamp: datetime


class StoreAPIAdapter(ABC):
    """
    Abstract base class for store-specific inventory API adapters.

    Concrete subclasses (e.g. HomeDepotAdapter, LowesAdapter) implement
    ``check_stock`` to query their respective store APIs and return a list
    of ``StockResult`` objects normalised to the common schema.

    Usage
    -----
    Adapters are instantiated by InventoryService and called concurrently
    via ``asyncio.gather`` with a per-adapter 5-second timeout (Requirement
    2.4).  A timed-out or errored adapter is marked as "unavailable" and
    does not prevent results from other adapters from being processed
    (Requirement 2.4 / Design Property 5).
    """

    @abstractmethod
    async def check_stock(
        self,
        store_id: str,
        bom_items: list,
    ) -> list[StockResult]:
        """
        Query a single store for the availability of the given BOM items.

        Parameters
        ----------
        store_id:
            Identifier of the specific store location to query.
        bom_items:
            List of ``BOMItem`` instances (defined in the ORM models) whose
            availability should be checked.  Client-supplied items are
            excluded by ``InventoryService`` before this method is called
            (Requirement 2.5).

        Returns
        -------
        list[StockResult]
            One ``StockResult`` per queried BOM item.  Items that the store
            does not carry should be represented with ``in_stock=False`` and
            ``quantity_available=0``.

        Raises
        ------
        asyncio.TimeoutError
            Propagated when the HTTP call exceeds the 5-second budget imposed
            by the caller (InventoryService).  Do not catch this inside the
            adapter — let it bubble up so InventoryService can mark the store
            as unavailable and continue with remaining stores.
        aiohttp.ClientError
            Any network-level error; callers treat this the same as a timeout.
        """
