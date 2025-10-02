from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

# Import correct dependencies
from app.db.session import get_db  # Or use app.db.database depending on your setup
from app.core.auth import get_current_active_user, require_artisan, require_admin_or_self, require_admin
from app.models.user import User
from app.schemas.artisan import (
    ArtisanProfileCreate, 
    ArtisanProfileUpdate, 
    ArtisanOut,
    ArtisanLocationUpdate,
    NearbyArtisansRequest,
    NearbyArtisansResponse,
    GeolocationRequest,
    GeolocationResponse,
    PaginatedArtisans,
)
from app.services.artisan import ArtisanService
from app.services.geolocation import geolocation_service
from app.services.artisan_service import find_nearby_artisans_cached  # from Discovery&Filtering branch

router = APIRouter(prefix="/artisans")

# ✅ GET-based nearby artisans search (from Discovery&Filtering)
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

# ✅ POST-based nearby artisans search (from main)
@router.post("/nearby", response_model=NearbyArtisansResponse)
async def find_nearby_artisans(
    request: NearbyArtisansRequest,
    db: Session = Depends(get_db)
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
    current_user: User = Depends(require_artisan)
):
    """Create artisan profile - artisan only"""
    service = ArtisanService(db)
    existing = service.get_artisan_by_user_id(current_user.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Artisan profile already exists")
    artisan = await service.create_artisan_profile(current_user.id, profile_data)
    if not artisan:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create artisan profile")
    return artisan

@router.put("/profile", response_model=ArtisanOut)
async def update_artisan_profile(
    profile_data: ArtisanProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Update artisan profile - artisan only"""
    service = ArtisanService(db)
    artisan = service.get_artisan_by_user_id(current_user.id)
    if not artisan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan profile not found")
    updated_artisan = await service.update_artisan_profile(artisan.id, profile_data)
    if not updated_artisan:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update artisan profile")
    return updated_artisan

@router.put("/location", response_model=ArtisanOut)
async def update_artisan_location(
    location_data: ArtisanLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Update artisan location with optional geocoding - artisan only"""
    service = ArtisanService(db)
    artisan = service.get_artisan_by_user_id(current_user.id)
    if not artisan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan profile not found")
    if location_data.location and not (location_data.latitude and location_data.longitude):
        updated_artisan = await service.geocode_and_update_location(artisan.id, location_data.location)
        if not updated_artisan:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to geocode address")
        return updated_artisan
    profile_update = ArtisanProfileUpdate(
        location=location_data.location,
        latitude=location_data.latitude,
        longitude=location_data.longitude
    )
    updated_artisan = await service.update_artisan_profile(artisan.id, profile_update)
    if not updated_artisan:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update location")
    return updated_artisan

@router.post("/geocode", response_model=GeolocationResponse)
async def geocode_address(
    request: GeolocationRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Convert address to coordinates - authenticated users only"""
    geo_result = await geolocation_service.geocode_address(request.address)
    if not geo_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found or geocoding failed")
    return geo_result

@router.put("/availability")
def update_availability(
    availability_data: dict,  # Consider defining a proper schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Update artisan availability - artisan only"""
    return {
        "message": "Availability updated successfully",
        "artisan_id": current_user.id,
        "availability": availability_data
    }

@router.get("/my-portfolio")
def get_my_portfolio(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Get current artisan's portfolio"""
    return {
        "message": f"Portfolio for artisan {current_user.id}",
        "artisan_name": current_user.full_name,
        "portfolio_items": []  # TODO: Implement DB fetch
    }

@router.post("/portfolio/add")
def add_portfolio_item(
    portfolio_item: dict,  # Replace with actual schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Add portfolio item - artisan only"""
    return {
        "message": "Portfolio item added successfully",
        "artisan_id": current_user.id,
        "portfolio_item": portfolio_item
    }

@router.get("/my-bookings")
def get_artisan_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Get bookings assigned to current artisan"""
    return {
        "message": f"Bookings for artisan {current_user.id}",
        "artisan_name": current_user.full_name,
        "bookings": []  # TODO: Implement DB fetch
    }

@router.get("/", response_model=List[ArtisanOut])
def list_artisans(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    specialties: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    is_available: Optional[bool] = Query(None),
    has_location: Optional[bool] = Query(None)
):
    """List all artisans with optional filters - public endpoint"""
    service = ArtisanService(db)
    artisans = service.list_artisans(
        skip=skip,
        limit=limit,
        specialties=specialties,
        min_rating=min_rating,
        is_available=is_available,
        has_location=has_location
    )
    return artisans

@router.get("/{artisan_id}/profile")
def get_artisan_profile(
    artisan_id: int,
    db: Session = Depends(get_db)
):
    """Get specific artisan profile - public endpoint"""
    return {
        "message": f"Profile for artisan {artisan_id}",
        "profile": {}  # TODO: Implement DB fetch
    }

@router.delete("/{artisan_id}")
def delete_artisan(
    artisan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete artisan account - admin only"""
    return {
        "message": f"Artisan {artisan_id} deleted by admin {current_user.id}",
        "deleted_by": current_user.full_name
    }
