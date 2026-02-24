import json as _json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.auth import (
    get_current_active_user,
    require_admin,
    require_artisan,
)

# Import correct dependencies
from app.db.session import get_db  # Or use app.db.database depending on your setup
from app.models.artisan import Artisan
from app.models.portfolio import Portfolio
from app.models.user import User
from app.schemas.artisan import (
    ArtisanLocationUpdate,
    ArtisanOut,
    ArtisanProfileCreate,
    ArtisanProfileResponse,
    ArtisanProfileUpdate,
    GeolocationRequest,
    GeolocationResponse,
    NearbyArtisansRequest,
    NearbyArtisansResponse,
    PaginatedArtisans,
)
from app.services.artisan import ArtisanService
from app.services.geolocation import geolocation_service

# from app.services.artisan_service import find_nearby_artisans_cached  # Broken import removed

router = APIRouter(prefix="/artisans")


@router.get("/counts")
def get_artisan_counts(db: Session = Depends(get_db)):
    """Return available artisan counts grouped by specialty for the landing page.

    Parses the JSON-encoded ``specialties`` column and returns a dict whose keys
    are lower-cased specialty names and whose values are the number of *available*
    artisans that list that specialty.  A ``total`` key gives the overall count of
    available artisans regardless of specialty.
    """
    artisans = (
        db.query(Artisan.specialties)
        .filter(Artisan.is_available == True)  # noqa: E712
        .all()
    )

    counts: dict[str, int] = {}
    for (raw,) in artisans:
        if not raw:
            continue
        try:
            specs = _json.loads(raw)
            if isinstance(specs, list):
                for s in specs:
                    key = str(s).strip().lower()
                    counts[key] = counts.get(key, 0) + 1
            else:
                key = str(specs).strip().lower()
                counts[key] = counts.get(key, 0) + 1
        except Exception:
            continue

    counts["total"] = len(artisans)
    return counts


# ✅ GET-based nearby artisans search (from Discovery&Filtering)
@router.get("/nearby", response_model=PaginatedArtisans)
async def get_nearby_artisans(
    *,
    db: Session = Depends(get_db),
    lat: float = Query(..., description="Latitude of the client location"),
    lon: float = Query(..., description="Longitude of the client location"),
    radius_km: float = Query(
        25.0, ge=0, le=200, description="Search radius in kilometers"
    ),
    skill: str
    | None = Query(None, description="Filter by skill keyword (e.g., plumber)"),
    min_rating: float
    | None = Query(None, ge=0, le=5, description="Minimum average rating"),
    available: bool | None = Query(None, description="Filter by current availability"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """
    Discover artisans nearby with optional filters for skill, minimum rating, and availability.
    Results are paginated and sorted by distance (asc) then rating (desc).
    """
    service = ArtisanService(db)
    request = NearbyArtisansRequest(
        latitude=lat,
        longitude=lon,
        radius_km=radius_km,
        specialties=[skill] if skill else None,
        min_rating=min_rating,
        is_available=available if available is not None else True,
        limit=page_size * page,  # Fetch enough for pagination
    )

    result = await service.find_nearby_artisans(request)

    # Manual pagination since service returns all matches within limit
    all_items = result.get("artisans", [])
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = all_items[start:end]

    return {
        "items": paginated_items,
        "total": result.get("total_found", 0),
        "page": page,
        "page_size": page_size,
    }


# ✅ POST-based nearby artisans search (from main)
@router.post("/nearby", response_model=NearbyArtisansResponse)
async def find_nearby_artisans(
    request: NearbyArtisansRequest, db: Session = Depends(get_db)
):
    """Find nearby artisans - public endpoint"""
    service = ArtisanService(db)
    result = await service.find_nearby_artisans(request)
    return result


# Other artisan-related endpoints from main
@router.post("/profile", response_model=ArtisanOut)
async def create_artisan_profile(
    profile_data: ArtisanProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """Create artisan profile - artisan only"""
    service = ArtisanService(db)
    existing = service.get_artisan_by_user_id(current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artisan profile already exists",
        )
    artisan = await service.create_artisan_profile(current_user.id, profile_data)
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create artisan profile",
        )
    return artisan


@router.put("/profile", response_model=ArtisanOut)
async def update_artisan_profile(
    profile_data: ArtisanProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """Update artisan profile - artisan only"""
    service = ArtisanService(db)
    artisan = service.get_artisan_by_user_id(current_user.id)
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artisan profile not found"
        )
    updated_artisan = await service.update_artisan_profile(artisan.id, profile_data)
    if not updated_artisan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update artisan profile",
        )
    return updated_artisan


@router.put("/location", response_model=ArtisanOut)
async def update_artisan_location(
    location_data: ArtisanLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """Update artisan location with optional geocoding - artisan only"""
    service = ArtisanService(db)
    artisan = service.get_artisan_by_user_id(current_user.id)
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artisan profile not found"
        )
    if location_data.location and not (
        location_data.latitude and location_data.longitude
    ):
        updated_artisan = await service.geocode_and_update_location(
            artisan.id, location_data.location
        )
        if not updated_artisan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to geocode address",
            )
        return updated_artisan
    profile_update = ArtisanProfileUpdate(
        location=location_data.location,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
    )
    updated_artisan = await service.update_artisan_profile(artisan.id, profile_update)
    if not updated_artisan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location",
        )
    return updated_artisan


@router.post("/geocode", response_model=GeolocationResponse)
async def geocode_address(
    request: GeolocationRequest, current_user: User = Depends(get_current_active_user)
):
    """Convert address to coordinates - authenticated users only"""
    geo_result = await geolocation_service.geocode_address(request.address)
    if not geo_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found or geocoding failed",
        )
    return geo_result


@router.put("/availability")
def update_availability(
    availability_data: dict,  # Consider defining a proper schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """Update artisan availability - artisan only"""
    return {
        "message": "Availability updated successfully",
        "artisan_id": current_user.id,
        "availability": availability_data,
    }


@router.get("/my-portfolio")
def get_my_portfolio(
    db: Session = Depends(get_db), current_user: User = Depends(require_artisan)
):
    """Get current artisan's portfolio"""
    # TODO: Implement Portfolio model and DB table
    # For now, return empty list as functionality is not yet supported in DB
    return {
        "message": f"Portfolio for artisan {current_user.id}",
        "artisan_name": current_user.full_name,
        "portfolio_items": [],
    }


@router.post("/portfolio/add")
def add_portfolio_item(
    portfolio_item: dict,  # Replace with actual schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """Add portfolio item - artisan only"""
    # TODO: Implement Portfolio model and DB table
    return {
        "message": "Portfolio item added successfully (simulation)",
        "artisan_id": current_user.id,
        "portfolio_item": portfolio_item,
    }


@router.get("/my-bookings")
def get_artisan_bookings(
    db: Session = Depends(get_db), current_user: User = Depends(require_artisan)
):
    """Get bookings assigned to current artisan"""
    service = ArtisanService(db)
    artisan = service.get_artisan_by_user_id(current_user.id)
    if not artisan:
        raise HTTPException(status_code=404, detail="Artisan profile not found")

    from app.models.booking import Booking

    bookings = db.query(Booking).filter(Booking.artisan_id == artisan.id).all()

    return {
        "message": f"Bookings for artisan {current_user.id}",
        "artisan_name": current_user.full_name,
        "bookings": bookings,
    }


@router.get("/", response_model=list[ArtisanOut])
def list_artisans(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    specialties: list[str] | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=5),
    is_available: bool | None = Query(None),
    has_location: bool | None = Query(None),
):
    """List all artisans with optional filters - public endpoint"""
    service = ArtisanService(db)
    artisans = service.list_artisans(
        skip=skip,
        limit=limit,
        specialties=specialties,
        min_rating=min_rating,
        is_available=is_available,
        has_location=has_location,
    )
    return artisans


@router.get("/{artisan_id}/profile", response_model=ArtisanProfileResponse)
def get_artisan_profile(artisan_id: int, db: Session = Depends(get_db)):
    """Get specific artisan profile - public endpoint"""
    # Fetch artisan with user data eagerly to avoid N+1
    artisan = (
        db.query(Artisan)
        .options(joinedload(Artisan.user))
        .filter(Artisan.id == artisan_id)
        .first()
    )

    if not artisan or not artisan.user:
        raise HTTPException(status_code=404, detail="Artisan not found")

    # Fetch top 5 most recent portfolio items
    portfolio_items = (
        db.query(Portfolio)
        .filter(Portfolio.artisan_id == artisan_id)
        .order_by(Portfolio.created_at.desc())
        .limit(5)
        .all()
    )

    # Process specialties JSON
    specialty_str = None
    if artisan.specialties:
        try:
            import json

            specs = json.loads(artisan.specialties)
            if isinstance(specs, list):
                # Take the first one as primary or join them
                specialty_str = specs[0] if specs else None
            else:
                specialty_str = str(specs)
        except Exception:
            # Fallback if text is not JSON
            specialty_str = artisan.specialties

    # Construct response
    return {
        "id": artisan.id,
        "name": artisan.user.full_name,
        "avatar": artisan.user.avatar,
        "specialty": specialty_str,
        "rate": artisan.hourly_rate,
        "bio": artisan.description,
        "portfolio": portfolio_items,
        "average_rating": artisan.rating,
        "location": artisan.location,
    }


@router.delete("/{artisan_id}")
def delete_artisan(
    artisan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete artisan account - admin only"""
    return {
        "message": f"Artisan {artisan_id} deleted by admin {current_user.id}",
        "deleted_by": current_user.full_name,
    }
