from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians
from typing import NamedTuple


class BoundingBox(NamedTuple):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


@dataclass
class RouteCorridorResult:
    origin: tuple[float, float]          # (lat, lon)
    destination: tuple[float, float]     # (lat, lon)
    corridor_half_width_m: float
    bounding_box: BoundingBox


class RouteService:
    """Computes a geographic corridor (bounding box) around the straight-line
    segment between two GPS coordinates."""

    # Metres per degree of latitude (approximately constant)
    _M_PER_DEG_LAT: float = 111_320.0

    def compute_corridor(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        half_width_m: float = 500.0,
    ) -> RouteCorridorResult:
        """Return a RouteCorridorResult whose bounding_box is the axis-aligned
        bounding box of the two endpoints expanded by *half_width_m* in every
        direction.

        Degree conversion uses the Haversine approximation:
          1° latitude  ≈ 111 320 m
          1° longitude ≈ 111 320 * cos(mean_lat) m
        """
        mean_lat = (origin_lat + dest_lat) / 2.0
        delta_lat_deg = half_width_m / self._M_PER_DEG_LAT
        delta_lon_deg = half_width_m / (self._M_PER_DEG_LAT * cos(radians(mean_lat)))

        min_lat = min(origin_lat, dest_lat) - delta_lat_deg
        max_lat = max(origin_lat, dest_lat) + delta_lat_deg
        min_lon = min(origin_lon, dest_lon) - delta_lon_deg
        max_lon = max(origin_lon, dest_lon) + delta_lon_deg

        return RouteCorridorResult(
            origin=(origin_lat, origin_lon),
            destination=(dest_lat, dest_lon),
            corridor_half_width_m=half_width_m,
            bounding_box=BoundingBox(min_lat, min_lon, max_lat, max_lon),
        )

    def point_in_corridor(
        self, lat: float, lon: float, corridor: RouteCorridorResult
    ) -> bool:
        """Return True if (lat, lon) falls within the corridor's bounding box."""
        bb = corridor.bounding_box
        return bb.min_lat <= lat <= bb.max_lat and bb.min_lon <= lon <= bb.max_lon


# Module-level singleton
route_service = RouteService()
