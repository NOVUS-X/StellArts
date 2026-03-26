"""Unit tests for RouteService corridor computation (Task 3)."""
from __future__ import annotations

import math

import pytest

from app.services.route_service import BoundingBox, RouteCorridorResult, RouteService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

svc = RouteService()

# Approximate metres-per-degree constants (same as implementation)
_M_PER_DEG_LAT = 111_320.0


def _expected_delta_lat(half_width_m: float) -> float:
    return half_width_m / _M_PER_DEG_LAT


def _expected_delta_lon(half_width_m: float, mean_lat: float) -> float:
    return half_width_m / (_M_PER_DEG_LAT * math.cos(math.radians(mean_lat)))


# ---------------------------------------------------------------------------
# compute_corridor — bounding box dimensions
# ---------------------------------------------------------------------------


class TestComputeCorridor:
    def test_returns_route_corridor_result(self):
        result = svc.compute_corridor(51.5, -0.1, 51.6, -0.2)
        assert isinstance(result, RouteCorridorResult)
        assert isinstance(result.bounding_box, BoundingBox)

    def test_origin_and_destination_stored(self):
        result = svc.compute_corridor(10.0, 20.0, 11.0, 21.0)
        assert result.origin == (10.0, 20.0)
        assert result.destination == (11.0, 21.0)

    def test_half_width_stored(self):
        result = svc.compute_corridor(0.0, 0.0, 1.0, 1.0, half_width_m=1000.0)
        assert result.corridor_half_width_m == 1000.0

    def test_default_half_width_is_500(self):
        result = svc.compute_corridor(0.0, 0.0, 1.0, 1.0)
        assert result.corridor_half_width_m == 500.0

    def test_bounding_box_expands_by_correct_lat_delta(self):
        origin_lat, origin_lon = 51.5, -0.1
        dest_lat, dest_lon = 51.6, -0.2
        half_width_m = 500.0

        result = svc.compute_corridor(origin_lat, origin_lon, dest_lat, dest_lon, half_width_m)
        bb = result.bounding_box

        expected_delta_lat = _expected_delta_lat(half_width_m)
        assert bb.min_lat == pytest.approx(min(origin_lat, dest_lat) - expected_delta_lat, rel=1e-6)
        assert bb.max_lat == pytest.approx(max(origin_lat, dest_lat) + expected_delta_lat, rel=1e-6)

    def test_bounding_box_expands_by_correct_lon_delta(self):
        origin_lat, origin_lon = 51.5, -0.1
        dest_lat, dest_lon = 51.6, -0.2
        half_width_m = 500.0
        mean_lat = (origin_lat + dest_lat) / 2.0

        result = svc.compute_corridor(origin_lat, origin_lon, dest_lat, dest_lon, half_width_m)
        bb = result.bounding_box

        expected_delta_lon = _expected_delta_lon(half_width_m, mean_lat)
        assert bb.min_lon == pytest.approx(min(origin_lon, dest_lon) - expected_delta_lon, rel=1e-6)
        assert bb.max_lon == pytest.approx(max(origin_lon, dest_lon) + expected_delta_lon, rel=1e-6)

    def test_same_origin_and_destination(self):
        """A zero-length route should still produce a valid bounding box."""
        result = svc.compute_corridor(48.8566, 2.3522, 48.8566, 2.3522, half_width_m=200.0)
        bb = result.bounding_box
        assert bb.max_lat > bb.min_lat
        assert bb.max_lon > bb.min_lon

    def test_larger_half_width_produces_larger_box(self):
        narrow = svc.compute_corridor(0.0, 0.0, 1.0, 1.0, half_width_m=100.0)
        wide = svc.compute_corridor(0.0, 0.0, 1.0, 1.0, half_width_m=5000.0)
        assert wide.bounding_box.min_lat < narrow.bounding_box.min_lat
        assert wide.bounding_box.max_lat > narrow.bounding_box.max_lat


# ---------------------------------------------------------------------------
# point_in_corridor
# ---------------------------------------------------------------------------


class TestPointInCorridor:
    def _corridor(self, half_width_m: float = 500.0) -> RouteCorridorResult:
        # London → slightly north-east
        return svc.compute_corridor(51.5, -0.1, 51.6, 0.0, half_width_m=half_width_m)

    def test_midpoint_is_inside(self):
        corridor = self._corridor()
        mid_lat = (51.5 + 51.6) / 2
        mid_lon = (-0.1 + 0.0) / 2
        assert svc.point_in_corridor(mid_lat, mid_lon, corridor) is True

    def test_origin_is_inside(self):
        corridor = self._corridor()
        assert svc.point_in_corridor(51.5, -0.1, corridor) is True

    def test_destination_is_inside(self):
        corridor = self._corridor()
        assert svc.point_in_corridor(51.6, 0.0, corridor) is True

    def test_point_far_north_is_outside(self):
        corridor = self._corridor()
        assert svc.point_in_corridor(55.0, -0.05, corridor) is False

    def test_point_far_east_is_outside(self):
        corridor = self._corridor()
        assert svc.point_in_corridor(51.55, 10.0, corridor) is False

    def test_point_just_outside_min_lat(self):
        corridor = self._corridor(half_width_m=500.0)
        just_outside = corridor.bounding_box.min_lat - 0.0001
        assert svc.point_in_corridor(just_outside, -0.05, corridor) is False

    def test_point_just_outside_max_lat(self):
        corridor = self._corridor(half_width_m=500.0)
        just_outside = corridor.bounding_box.max_lat + 0.0001
        assert svc.point_in_corridor(just_outside, -0.05, corridor) is False

    def test_point_on_boundary_is_inside(self):
        corridor = self._corridor(half_width_m=500.0)
        bb = corridor.bounding_box
        # Exactly on the min_lat boundary
        assert svc.point_in_corridor(bb.min_lat, (bb.min_lon + bb.max_lon) / 2, corridor) is True

    def test_narrow_corridor_excludes_wider_point(self):
        # Route along the equator; test a point 0.01° north (~1.1 km)
        narrow = svc.compute_corridor(0.0, 0.0, 0.0, 1.0, half_width_m=100.0)
        wide = svc.compute_corridor(0.0, 0.0, 0.0, 1.0, half_width_m=200_000.0)
        # 0.01° ≈ 1 113 m — outside narrow (100 m), inside wide (200 km)
        assert svc.point_in_corridor(0.01, 0.5, narrow) is False
        assert svc.point_in_corridor(0.01, 0.5, wide) is True
