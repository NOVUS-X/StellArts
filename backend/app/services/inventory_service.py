"""
InventoryService — cross-references a Bill of Materials with stores
located along the artisan's route.

Flow
----
1. Caller provides artisan coordinates, job-site coordinates, and a list of
   required materials (the BOM).
2. RoutingService builds a corridor of waypoints.
3. All Store rows are loaded; those within the corridor are kept.
4. Each on-route store's inventory_json is scanned for BOM items.
5. Matches are returned as StoreMatch objects ready for notification.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.store import Store
from app.services.routing_service import Coordinate, RoutingService

logger = logging.getLogger(__name__)


@dataclass
class BOMItem:
    """A single line in the Bill of Materials."""

    sku: str
    name: str
    quantity_needed: int = 1


@dataclass
class StoreMatch:
    """A store that stocks one or more required BOM items."""

    store_id: str
    store_name: str
    store_address: str
    distance_meters: float
    items_found: list[dict] = field(default_factory=list)
    # Deep-link / pre-pay URL for the notification
    prepay_url: str = ""


class InventoryService:
    DEFAULT_CORRIDOR_METERS = 500.0  # 500 m either side of the route

    def __init__(self, db: Session):
        self.db = db
        self.routing = RoutingService()

    def check_route(
        self,
        artisan_lat: float,
        artisan_lon: float,
        job_lat: float,
        job_lon: float,
        bom: list[BOMItem],
        corridor_meters: float = DEFAULT_CORRIDOR_METERS,
        client_supplied: bool = False,
    ) -> list[StoreMatch]:
        """
        Main entry point.

        Returns a list of StoreMatch objects for stores on the route that
        stock at least one BOM item.  Returns an empty list immediately if
        `client_supplied` is True (client override).
        """
        if client_supplied:
            logger.info("Client indicated materials are already supplied — skipping.")
            return []

        if not bom:
            return []

        origin = Coordinate(lat=artisan_lat, lon=artisan_lon)
        destination = Coordinate(lat=job_lat, lon=job_lon)
        waypoints = self.routing.build_corridor(origin, destination)

        stores: list[Store] = self.db.query(Store).all()
        matches: list[StoreMatch] = []

        for store in stores:
            if not self.routing.store_is_on_route(
                store.latitude, store.longitude, waypoints, corridor_meters
            ):
                continue

            # Find the closest waypoint distance for display
            store_coord = Coordinate(lat=store.latitude, lon=store.longitude)
            min_dist = min(
                self.routing.haversine_meters(wp, store_coord) for wp in waypoints
            )

            items_found = self._match_bom(store, bom)
            if not items_found:
                continue

            prepay_url = self._build_prepay_url(store, items_found)
            matches.append(
                StoreMatch(
                    store_id=str(store.id),
                    store_name=store.name,
                    store_address=store.address,
                    distance_meters=round(min_dist, 1),
                    items_found=items_found,
                    prepay_url=prepay_url,
                )
            )

        # Sort by distance so the closest store appears first
        matches.sort(key=lambda m: m.distance_meters)
        return matches

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _match_bom(self, store: Store, bom: list[BOMItem]) -> list[dict]:
        """Return inventory entries that satisfy at least one BOM item."""
        if not store.inventory_json:
            return []

        try:
            inventory: list[dict] = json.loads(store.inventory_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Store %s has invalid inventory_json", store.id)
            return []

        bom_skus = {item.sku.lower() for item in bom}
        bom_names = {item.name.lower() for item in bom}

        found = []
        for entry in inventory:
            sku = str(entry.get("sku", "")).lower()
            name = str(entry.get("name", "")).lower()
            qty = int(entry.get("quantity", 0))
            if qty <= 0:
                continue
            if sku in bom_skus or any(kw in name for kw in bom_names):
                found.append(entry)

        return found

    @staticmethod
    def _build_prepay_url(store: Store, items: list[dict]) -> str:
        """Build a deep-link URL for the pre-pay action in the notification."""
        skus = ",".join(str(i.get("sku", "")) for i in items)
        store_ref = store.external_id or str(store.id)
        return f"/inventory/prepay?store={store_ref}&skus={skus}"
