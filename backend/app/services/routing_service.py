"""
RoutingService: computes a route polyline between two geographic coordinates
by wrapping an external routing provider (OpenRouteService or Google Maps).

Requirements: 1.1, 1.4
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import aiohttp


class RoutingError(Exception):
    """Raised when routing cannot be computed (missing GPS, provider failure, etc.)."""


@dataclass
class Coordinate:
    """A geographic point expressed as WGS-84 latitude/longitude."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"Invalid latitude: {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"Invalid longitude: {self.longitude}")


@dataclass
class RouteResult:
    """Result of a successful route computation."""

    polyline: dict          # GeoJSON LineString {"type": "LineString", "coordinates": [...]}
    duration_seconds: int
    distance_meters: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ORS_BASE = "https://api.openrouteservice.org/v2/directions/driving-car"
_GMAPS_BASE = "https://maps.googleapis.com/maps/api/directions/json"


def _ors_api_key() -> str | None:
    return os.environ.get("ORS_API_KEY")


def _gmaps_api_key() -> str | None:
    return os.environ.get("GOOGLE_MAPS_API_KEY")


def _decode_google_polyline(encoded: str) -> list[list[float]]:
    """Decode a Google Maps encoded polyline into [[lng, lat], ...] pairs."""
    coords: list[list[float]] = []
    index = 0
    lat = 0
    lng = 0
    while index < len(encoded):
        # latitude
        result, shift = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        # longitude
        result, shift = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng

        coords.append([lng / 1e5, lat / 1e5])
    return coords


# ---------------------------------------------------------------------------
# RoutingService
# ---------------------------------------------------------------------------


class RoutingService:
    """
    Computes a driving route between two coordinates.

    Provider selection (in priority order):
      1. OpenRouteService  — if ORS_API_KEY env var is set
      2. Google Maps       — if GOOGLE_MAPS_API_KEY env var is set
      3. Straight-line fallback (two-point LineString) — for environments
         without API keys (e.g. tests / local dev without credentials)

    Raises RoutingError if:
      - origin is None (GPS unavailable)
      - the external provider call fails or returns an error
    """

    async def compute_route(
        self,
        origin: Coordinate | None,
        destination: Coordinate,
    ) -> RouteResult:
        """
        Compute a driving route from *origin* to *destination*.

        Parameters
        ----------
        origin:
            The artisan's current GPS location.  Pass ``None`` to simulate
            an unavailable GPS fix — a ``RoutingError`` will be raised.
        destination:
            The job-site location.

        Returns
        -------
        RouteResult
            GeoJSON LineString polyline plus duration and distance estimates.

        Raises
        ------
        RoutingError
            When origin is None or the routing provider returns an error.
        """
        if origin is None:
            raise RoutingError("Artisan GPS location is unavailable")

        ors_key = _ors_api_key()
        gmaps_key = _gmaps_api_key()

        if ors_key:
            return await self._compute_via_ors(origin, destination, ors_key)
        if gmaps_key:
            return await self._compute_via_gmaps(origin, destination, gmaps_key)

        # Fallback: straight-line two-point LineString (no external call)
        return self._straight_line_fallback(origin, destination)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _compute_via_ors(
        self,
        origin: Coordinate,
        destination: Coordinate,
        api_key: str,
    ) -> RouteResult:
        """Call OpenRouteService Directions API."""
        payload = {
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "format": "geojson",
        }
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    _ORS_BASE, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RoutingError(
                            f"OpenRouteService returned HTTP {resp.status}: {text}"
                        )
                    data = await resp.json()
        except aiohttp.ClientError as exc:
            raise RoutingError(f"OpenRouteService request failed: {exc}") from exc

        try:
            feature = data["features"][0]
            geometry = feature["geometry"]  # GeoJSON LineString
            props = feature["properties"]["segments"][0]
            return RouteResult(
                polyline=geometry,
                duration_seconds=int(props["duration"]),
                distance_meters=int(props["distance"]),
            )
        except (KeyError, IndexError) as exc:
            raise RoutingError(
                f"Unexpected OpenRouteService response structure: {exc}"
            ) from exc

    async def _compute_via_gmaps(
        self,
        origin: Coordinate,
        destination: Coordinate,
        api_key: str,
    ) -> RouteResult:
        """Call Google Maps Directions API."""
        params = {
            "origin": f"{origin.latitude},{origin.longitude}",
            "destination": f"{destination.latitude},{destination.longitude}",
            "mode": "driving",
            "key": api_key,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    _GMAPS_BASE, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RoutingError(
                            f"Google Maps returned HTTP {resp.status}: {text}"
                        )
                    data = await resp.json()
        except aiohttp.ClientError as exc:
            raise RoutingError(f"Google Maps request failed: {exc}") from exc

        status = data.get("status")
        if status != "OK":
            raise RoutingError(f"Google Maps Directions API error: {status}")

        try:
            route = data["routes"][0]
            leg = route["legs"][0]
            encoded = route["overview_polyline"]["points"]
            coords = _decode_google_polyline(encoded)
            polyline = {"type": "LineString", "coordinates": coords}
            return RouteResult(
                polyline=polyline,
                duration_seconds=leg["duration"]["value"],
                distance_meters=leg["distance"]["value"],
            )
        except (KeyError, IndexError) as exc:
            raise RoutingError(
                f"Unexpected Google Maps response structure: {exc}"
            ) from exc

    @staticmethod
    def _straight_line_fallback(
        origin: Coordinate,
        destination: Coordinate,
    ) -> RouteResult:
        """
        Return a minimal two-point LineString when no API key is configured.
        Distance is approximated via the Haversine formula; duration is
        estimated at 50 km/h average speed.
        """
        import math

        lat1 = math.radians(origin.latitude)
        lat2 = math.radians(destination.latitude)
        dlat = math.radians(destination.latitude - origin.latitude)
        dlon = math.radians(destination.longitude - origin.longitude)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance_m = int(6_371_000 * 2 * math.asin(math.sqrt(a)))
        duration_s = int(distance_m / (50_000 / 3600))  # 50 km/h

        polyline = {
            "type": "LineString",
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
        }
        return RouteResult(
            polyline=polyline,
            duration_seconds=duration_s,
            distance_meters=distance_m,
        )
