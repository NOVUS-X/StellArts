import hashlib
import json

from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import settings
from app.schemas.artisan import NearbyArtisansRequest
from app.services.artisan import ArtisanService

CACHE_TTL_SECONDS = getattr(settings, "NEARBY_CACHE_TTL", 60)


def _build_cache_key(request: NearbyArtisansRequest) -> str:
    """Build a deterministic cache key from search parameters."""
    key_data = {
        "lat": round(float(request.latitude), 4),  # 4dp ≈ 11m precision
        "lon": round(float(request.longitude), 4),
        "radius": request.radius_km,
        "specialties": sorted(request.specialties or []),  # order-independent
        "min_rating": request.min_rating,
        "available": request.is_available,
        "limit": request.limit,
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return f"nearby:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"


async def find_nearby_artisans_cached(
    db: Session,
    request: NearbyArtisansRequest,
    ttl: int = CACHE_TTL_SECONDS,
) -> dict:
    """Find nearby artisans with Redis result caching.

    Cache key is derived from search parameters (lat/lon rounded to 4dp,
    radius, specialties, rating, availability, limit). Results are cached for
    `ttl` seconds (default: settings.NEARBY_CACHE_TTL or 60s).

    Cache miss falls through to ArtisanService.find_nearby_artisans().
    Empty results are not cached to avoid persisting a stale "no artisans
    found" state that may change within the same TTL window.
    """
    cache_key = _build_cache_key(request)

    # Attempt cache hit
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    # Cache miss — run full query
    service = ArtisanService(db)
    result = await service.find_nearby_artisans(request)

    # Store result if non-empty
    if result.get("artisans"):
        await cache.set(cache_key, result, expire=ttl)

    return result
