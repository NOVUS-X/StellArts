from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.artisan import PaginatedArtisans
from app.services.artisan_service import find_nearby_artisans_cached

router = APIRouter(prefix="/artisans")


@router.get("/nearby", response_model=PaginatedArtisans)
async def get_nearby_artisans(
    *,
    db: Session = Depends(get_db),
    lat: float = Query(..., description="Latitude of the client location"),
    lon: float = Query(..., description="Longitude of the client location"),
    radius_km: float = Query(25.0, ge=0, le=200, description="Search radius in kilometers"),
    skill: Optional[str] = Query(None, description="Filter by skill keyword (e.g., plumber)"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum average rating"),
    available: Optional[bool] = Query(None, description="Filter by current availability"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """
    Discover artisans nearby with optional filters for skill, minimum rating, and availability.
    Results are paginated and sorted by distance (asc) then rating (desc).
    """
    result = await find_nearby_artisans_cached(
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
    return result
