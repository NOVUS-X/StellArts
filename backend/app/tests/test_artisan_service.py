"""Unit tests for artisan_service.find_nearby_artisans_cached and _build_cache_key."""
import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.artisan import NearbyArtisansRequest
from app.services.artisan import ArtisanService
from app.services.artisan_service import _build_cache_key, find_nearby_artisans_cached

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RESULT = {
    "artisans": [{"id": 1, "business_name": "Bob's Plumbing", "distance_km": 2.5}],
    "total_found": 1,
    "search_center": {"latitude": 1.0, "longitude": 1.0},
    "radius_km": 10.0,
}

EMPTY_RESULT = {
    "artisans": [],
    "total_found": 0,
    "search_center": {"latitude": 1.0, "longitude": 1.0},
    "radius_km": 10.0,
}


def make_request(**overrides) -> NearbyArtisansRequest:
    defaults = {"latitude": 1.0, "longitude": 1.0, "radius_km": 10.0, "limit": 20}
    defaults.update(overrides)
    return NearbyArtisansRequest(**defaults)


# ---------------------------------------------------------------------------
# Test 1: Cache miss calls ArtisanService.find_nearby_artisans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_miss_calls_service():
    db = MagicMock()
    request = make_request()

    with (
        patch("app.services.artisan_service.cache") as mock_cache,
        patch.object(
            ArtisanService,
            "find_nearby_artisans",
            new_callable=AsyncMock,
            return_value=SAMPLE_RESULT,
        ) as mock_service,
    ):
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)

        result = await find_nearby_artisans_cached(db, request)

    mock_service.assert_called_once_with(request)
    assert result == SAMPLE_RESULT


# ---------------------------------------------------------------------------
# Test 2: Cache hit does NOT call ArtisanService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_service():
    db = MagicMock()
    request = make_request()

    with (
        patch("app.services.artisan_service.cache") as mock_cache,
        patch.object(
            ArtisanService,
            "find_nearby_artisans",
            new_callable=AsyncMock,
        ) as mock_service,
    ):
        mock_cache.get = AsyncMock(return_value=SAMPLE_RESULT)

        result = await find_nearby_artisans_cached(db, request)

    mock_service.assert_not_called()
    assert result == SAMPLE_RESULT


# ---------------------------------------------------------------------------
# Test 3: Non-empty results are stored in cache on miss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_result_stored_in_cache_on_miss():
    db = MagicMock()
    request = make_request()

    with (
        patch("app.services.artisan_service.cache") as mock_cache,
        patch.object(
            ArtisanService,
            "find_nearby_artisans",
            new_callable=AsyncMock,
            return_value=SAMPLE_RESULT,
        ),
    ):
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)

        await find_nearby_artisans_cached(db, request)

    mock_cache.set.assert_called_once()
    call_args = mock_cache.set.call_args
    assert call_args[0][1] == SAMPLE_RESULT


# ---------------------------------------------------------------------------
# Test 4: Empty results are NOT cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_results_not_cached():
    db = MagicMock()
    request = make_request()

    with (
        patch("app.services.artisan_service.cache") as mock_cache,
        patch.object(
            ArtisanService,
            "find_nearby_artisans",
            new_callable=AsyncMock,
            return_value=EMPTY_RESULT,
        ),
    ):
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)

        await find_nearby_artisans_cached(db, request)

    mock_cache.set.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: Different search params produce different cache keys
# ---------------------------------------------------------------------------


def test_different_params_produce_different_keys():
    r1 = make_request(radius_km=10.0)
    r2 = make_request(radius_km=25.0)
    assert _build_cache_key(r1) != _build_cache_key(r2)


# ---------------------------------------------------------------------------
# Test 6: Nearby coordinates (within 4dp) share the same cache key
# ---------------------------------------------------------------------------


def test_nearby_coords_share_cache_key():
    # Differ only at the 5th decimal place — should round to the same 4dp bucket
    r1 = make_request(latitude=1.12345, longitude=1.12345, radius_km=10.0)
    r2 = make_request(latitude=1.12346, longitude=1.12346, radius_km=10.0)
    assert _build_cache_key(r1) == _build_cache_key(r2)
