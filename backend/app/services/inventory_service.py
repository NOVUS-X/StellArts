"""
InventoryService: orchestrates the route-corridor store discovery, BOM
cross-reference, and async fan-out to Store_API adapters.

Requirements: 1.2, 1.3, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.3
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.store_api_adapter import StockResult, StoreAPIAdapter
from app.services.routing_service import RouteResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BOMItem placeholder
# ---------------------------------------------------------------------------
# A full ORM model for bom_items will be added in a later task.  Until then
# this dataclass mirrors the columns that InventoryService needs.


@dataclass
class BOMItem:
    """
    Represents a single line item in a job's Bill of Materials.

    Fields mirror the ``bom_items`` table columns relevant to inventory
    checking.  The ``client_supplied`` flag is used to exclude items that
    the client has indicated they already possess (Requirements 2.5, 3.4).
    """

    id: UUID
    job_id: UUID
    part_number: str
    part_name: str
    quantity: int
    client_supplied: bool = False

    # Alias used by adapters (StockResult.bom_item_id references this)
    @property
    def bom_item_id(self) -> UUID:
        return self.id


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class StoreMatch:
    """
    Aggregated inventory results for a single store that has at least one
    BOM item in stock.
    """

    store_id: str
    store_name: str
    store_address: str
    results: list[StockResult] = field(default_factory=list)


@dataclass
class InventoryCheckResult:
    """
    Final output of a completed inventory check run.

    Attributes
    ----------
    job_id:
        The job whose BOM was checked.
    stores_queried:
        Total number of stores found within the route corridor.
    stores_unavailable:
        Number of stores whose adapter call timed out or raised an error.
    matches:
        Stores that returned at least one in-stock BOM item.
    """

    job_id: UUID
    stores_queried: int
    stores_unavailable: int
    matches: list[StoreMatch] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

def _build_adapter(api_adapter: str, api_config: dict | None) -> StoreAPIAdapter:
    """
    Instantiate the correct StoreAPIAdapter subclass based on the store's
    ``api_adapter`` field value.

    Raises
    ------
    ValueError
        When no adapter is registered for the given identifier.
    """
    config = api_config or {}

    if api_adapter == "home_depot":
        from app.adapters.home_depot_adapter import HomeDepotAdapter
        return HomeDepotAdapter(config)

    raise ValueError(f"Unknown store adapter: {api_adapter!r}")


# ---------------------------------------------------------------------------
# InventoryService
# ---------------------------------------------------------------------------


class InventoryService:
    """
    Core orchestrator for the route-based inventory check pipeline.

    Responsibilities
    ----------------
    1. Query PostGIS for stores within ``corridor_meters`` of the route
       polyline (Requirements 1.2, 5.1).
    2. Fetch BOM items for the job, excluding client-supplied items
       (Requirements 2.1, 2.5, 3.4).
    3. Fan out async ``check_stock`` calls to each store's adapter with a
       per-adapter 5-second timeout (Requirements 2.2, 2.4).
    4. Mark timed-out or errored stores as unavailable; continue processing
       remaining stores (Requirement 2.4).
    5. Aggregate in-stock results into an ``InventoryCheckResult``
       (Requirements 2.3, 5.3).
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_inventory_check(
        self,
        job_id: UUID,
        route: RouteResult,
        corridor_meters: int = 500,
    ) -> InventoryCheckResult:
        """
        Execute a full inventory check for *job_id* along *route*.

        Parameters
        ----------
        job_id:
            UUID of the job whose BOM should be checked.
        route:
            Computed route result containing the GeoJSON LineString polyline.
        corridor_meters:
            Lateral buffer distance in metres around the route polyline.
            Defaults to 500 m (Requirement 1.3).

        Returns
        -------
        InventoryCheckResult
            Aggregated results including matched stores and unavailability
            counts.
        """
        # Step 1 — find stores in the route corridor (Requirements 1.2, 5.1)
        stores = self._query_corridor_stores(route, corridor_meters)

        if not stores:
            logger.info("No stores found within %dm corridor for job %s", corridor_meters, job_id)
            return InventoryCheckResult(
                job_id=job_id,
                stores_queried=0,
                stores_unavailable=0,
                matches=[],
            )

        # Step 2 — fetch BOM, exclude client-supplied items (Requirements 2.1, 2.5)
        bom_items = self._fetch_bom_items(job_id)
        queryable_items = [item for item in bom_items if not item.client_supplied]

        if not queryable_items:
            logger.info(
                "All BOM items are client-supplied for job %s; skipping store queries", job_id
            )
            return InventoryCheckResult(
                job_id=job_id,
                stores_queried=len(stores),
                stores_unavailable=0,
                matches=[],
            )

        # Step 3 — fan out async adapter calls (Requirements 2.2, 2.4)
        matches, unavailable_count = await self._fan_out_queries(stores, queryable_items)

        return InventoryCheckResult(
            job_id=job_id,
            stores_queried=len(stores),
            stores_unavailable=unavailable_count,
            matches=matches,
        )

    # ------------------------------------------------------------------
    # PostGIS corridor query
    # ------------------------------------------------------------------

    def _query_corridor_stores(
        self,
        route: RouteResult,
        corridor_meters: int,
    ) -> list:
        """
        Return all Store ORM rows whose location falls within
        ``corridor_meters`` of the route polyline.

        Uses the PostGIS query from the design document:

            SELECT s.*
            FROM stores s
            WHERE ST_Intersects(
                s.location::geography,
                ST_Buffer(
                    ST_GeomFromGeoJSON(:polyline)::geography,
                    :corridor_meters
                )
            );

        Requirements: 1.2, 5.1
        """
        from app.models.store import Store  # local import to avoid circular deps

        polyline_json = json.dumps(route.polyline)

        sql = text(
            """
            SELECT s.*
            FROM stores s
            WHERE ST_Intersects(
                s.location::geography,
                ST_Buffer(
                    ST_GeomFromGeoJSON(:polyline)::geography,
                    :corridor_meters
                )
            )
            """
        )

        rows = self._db.execute(
            sql,
            {"polyline": polyline_json, "corridor_meters": corridor_meters},
        ).mappings().all()

        # Convert raw row mappings to lightweight store dicts so the rest of
        # the service doesn't depend on the ORM session being open.
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # BOM retrieval
    # ------------------------------------------------------------------

    def _fetch_bom_items(self, job_id: UUID) -> list[BOMItem]:
        """
        Retrieve all BOM items for *job_id* from the database.

        Returns a list of ``BOMItem`` dataclasses.  The caller is responsible
        for filtering out client-supplied items before passing them to
        adapters (Requirement 2.5).

        Note: Until a full BOMItem ORM model is added, this method queries
        the ``bom_items`` table directly via raw SQL.
        """
        sql = text(
            """
            SELECT id, job_id, part_number, part_name, quantity, client_supplied
            FROM bom_items
            WHERE job_id = :job_id
            """
        )
        rows = self._db.execute(sql, {"job_id": str(job_id)}).mappings().all()

        return [
            BOMItem(
                id=UUID(str(row["id"])),
                job_id=UUID(str(row["job_id"])),
                part_number=row["part_number"],
                part_name=row["part_name"],
                quantity=row["quantity"],
                client_supplied=bool(row["client_supplied"]),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Async fan-out
    # ------------------------------------------------------------------

    async def _fan_out_queries(
        self,
        stores: list[dict],
        bom_items: list[BOMItem],
    ) -> tuple[list[StoreMatch], int]:
        """
        Concurrently query every store's adapter for the given BOM items.

        Each adapter call is wrapped in ``asyncio.wait_for`` with a 5-second
        timeout (Requirement 2.4).  Timed-out or errored stores are counted
        as unavailable; their failure does not prevent other stores from
        being processed (Design Property 5).

        Returns
        -------
        tuple[list[StoreMatch], int]
            (list of StoreMatch with at least one in-stock item, count of
            unavailable stores)
        """
        tasks = [
            asyncio.wait_for(
                self._query_single_store(store, bom_items),
                timeout=5.0,
            )
            for store in stores
        ]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        matches: list[StoreMatch] = []
        unavailable_count = 0

        for store, result in zip(stores, raw_results):
            store_id = str(store["id"])
            store_name = store.get("name", "")
            store_address = store.get("address", "")

            if isinstance(result, BaseException):
                logger.warning(
                    "Store %s (%s) unavailable: %s: %s",
                    store_id,
                    store_name,
                    type(result).__name__,
                    result,
                )
                unavailable_count += 1
                continue

            # Filter to only in-stock results (Requirement 2.3)
            in_stock = [r for r in result if r.in_stock]
            if in_stock:
                matches.append(
                    StoreMatch(
                        store_id=store_id,
                        store_name=store_name,
                        store_address=store_address,
                        results=in_stock,
                    )
                )

        return matches, unavailable_count

    async def _query_single_store(
        self,
        store: dict,
        bom_items: list[BOMItem],
    ) -> list[StockResult]:
        """
        Build the correct adapter for *store* and call ``check_stock``.

        Raises
        ------
        ValueError
            When the store's ``api_adapter`` value is not registered.
        Any exception raised by the adapter (propagated to ``_fan_out_queries``
        which treats it as an unavailable store).
        """
        adapter: StoreAPIAdapter = _build_adapter(
            store["api_adapter"],
            store.get("api_config"),
        )
        store_id = str(store["id"])
        return await adapter.check_stock(store_id, bom_items)
