"""
RoutingService — computes a geographic corridor between two coordinates.

The corridor is a set of interpolated waypoints along the straight-line path
from the artisan's current position to the job site.  Any store whose
lat/lon falls within `corridor_meters` of any waypoint is considered
"on the route".

This is a lightweight, dependency-free approximation.  A production
deployment can swap the `build_corridor` method for a real routing API
(e.g. OSRM, Google Directions) without changing the rest of the feature.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Coordinate:
    lat: float
    lon: float


class RoutingError(Exception):
    pass


class RoutingService:
    """Builds a list of waypoints along the artisan → job-site route."""

    def build_corridor(
        self,
        origin: Coordinate,
        destination: Coordinate,
        num_waypoints: int = 10,
    ) -> list[Coordinate]:
        """
        Return `num_waypoints` evenly-spaced points between origin and
        destination (inclusive of both endpoints).
        """
        if num_waypoints < 2:
            raise RoutingError("num_waypoints must be >= 2")

        waypoints: list[Coordinate] = []
        for i in range(num_waypoints):
            t = i / (num_waypoints - 1)
            waypoints.append(
                Coordinate(
                    lat=origin.lat + t * (destination.lat - origin.lat),
                    lon=origin.lon + t * (destination.lon - origin.lon),
                )
            )
        return waypoints

    @staticmethod
    def haversine_meters(a: Coordinate, b: Coordinate) -> float:
        """Great-circle distance in metres between two coordinates."""
        R = 6_371_000  # Earth radius in metres
        lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
        dlat = math.radians(b.lat - a.lat)
        dlon = math.radians(b.lon - a.lon)
        h = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(h))

    def store_is_on_route(
        self,
        store_lat: float,
        store_lon: float,
        waypoints: list[Coordinate],
        corridor_meters: float,
    ) -> bool:
        """Return True if the store is within `corridor_meters` of any waypoint."""
        store = Coordinate(lat=store_lat, lon=store_lon)
        return any(
            self.haversine_meters(wp, store) <= corridor_meters for wp in waypoints
        )
