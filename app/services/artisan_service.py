from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.models.artisan import Artisan
from app.core.cache import cache


EARTH_RADIUS_KM = 6371.0


def _distance_expr(lat: float, lon: float):
    """
    SQL expression for Haversine-based great-circle distance in KM between
    (lat, lon) and the artisan's (latitude, longitude).
    Note: Uses PostgreSQL trig functions via SQLAlchemy func.*
    """
    # acos(cos(radians(lat))*cos(radians(a.lat))*cos(radians(a.lon)-radians(lon)) + sin(radians(lat))*sin(radians(a.lat)))
    # Compute cosine of central angle
    cos_c = (
        func.cos(func.radians(lat))
        * func.cos(func.radians(Artisan.latitude))
        * func.cos(func.radians(Artisan.longitude) - func.radians(lon))
        + func.sin(func.radians(lat)) * func.sin(func.radians(Artisan.latitude))
    )
    # Clamp to [-1, 1] to avoid acos domain errors due to FP rounding
    cos_c_clamped = func.least(func.greatest(cos_c, -1.0), 1.0)
    return EARTH_RADIUS_KM * func.acos(cos_c_clamped)


def find_nearby_artisans(
    db: Session,
    *,
    lat: float,
    lon: float,
    radius_km: float = 25.0,
    skill: Optional[str] = None,
    min_rating: Optional[float] = None,
    available: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Query artisans near a coordinate, optionally filtering by skill, rating and availability.
    Returns a tuple of (items, total_count).
    """
    # Normalize pagination
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    dist_expr = _distance_expr(lat, lon).label("distance_km")

    # Base selectable with distance column
    base_stmt = select(
        Artisan.id,
        Artisan.business_name,
        Artisan.description,
        Artisan.specialties,
        Artisan.experience_years,
        Artisan.hourly_rate,
        Artisan.location,
        Artisan.latitude,
        Artisan.longitude,
        Artisan.is_verified,
        Artisan.is_available,
        Artisan.rating,
        Artisan.total_reviews,
        dist_expr,
    )

    # Filters
    conditions = []

    if skill:
        # specialties stored as text (JSON-ish); fallback to ILIKE contains
        conditions.append(Artisan.specialties.ilike(f"%{skill}%"))

    if min_rating is not None:
        conditions.append(Artisan.rating >= float(min_rating))

    if available is not None:
        conditions.append(Artisan.is_available == available)

    if radius_km is not None and radius_km > 0:
        # Filter by computed distance
        conditions.append(dist_expr <= float(radius_km))

    if conditions:
        base_stmt = base_stmt.where(*conditions)

    # Order: nearest first, then higher rating
    base_stmt = base_stmt.order_by(dist_expr.asc(), Artisan.rating.desc())

    # Total count: wrap as subquery for accuracy with distance/filters
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    # Pagination
    offset = (page - 1) * page_size
    paged_stmt = base_stmt.offset(offset).limit(page_size)

    rows = db.execute(paged_stmt).all()

    # Serialize
    items: List[Dict[str, Any]] = []
    for r in rows:
        item = {
            "id": r.id,
            "business_name": r.business_name,
            "description": r.description,
            "specialties": r.specialties,
            "experience_years": int(r.experience_years) if r.experience_years is not None else None,
            "hourly_rate": float(r.hourly_rate) if r.hourly_rate is not None else None,
            "location": r.location,
            "latitude": float(r.latitude) if r.latitude is not None else None,
            "longitude": float(r.longitude) if r.longitude is not None else None,
            "is_verified": bool(r.is_verified) if r.is_verified is not None else False,
            "is_available": bool(r.is_available) if r.is_available is not None else False,
            "rating": float(r.rating) if r.rating is not None else None,
            "total_reviews": int(r.total_reviews) if r.total_reviews is not None else 0,
            "distance_km": float(r.distance_km) if r.distance_km is not None else None,
        }
        items.append(item)

    return items, int(total)


async def find_nearby_artisans_cached(
    db: Session,
    *,
    lat: float,
    lon: float,
    radius_km: float = 25.0,
    skill: Optional[str] = None,
    min_rating: Optional[float] = None,
    available: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
    ttl_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Cached wrapper for nearby artisan discovery. Caches based on all filter params and pagination.
    """
    # Normalize inputs for cache key stability
    key_parts = {
        "lat": round(float(lat), 5),
        "lon": round(float(lon), 5),
        "radius": round(float(radius_km), 2) if radius_km is not None else None,
        "skill": (skill or "").strip().lower() if skill else "",
        "min_rating": round(float(min_rating), 2) if min_rating is not None else None,
        "available": available if available is not None else "any",
        "page": int(page),
        "size": int(page_size),
    }
    cache_key = (
        "artisans:nearby:" + 
        ":".join(f"{k}={v}" for k, v in key_parts.items())
    )

    cached = await cache.get(cache_key)
    if cached is not None:
        return cached  # already a dict as cache client JSON-decodes

    items, total = find_nearby_artisans(
        db,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        skill=skill,
        min_rating=min_rating,
        available=available,
        page=page,
        page_size=page_size,
    )

    payload = {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

    await cache.set(cache_key, payload, expire=ttl_seconds)

    return payload
