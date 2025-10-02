from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.core.auth import get_current_active_user, require_artisan, require_admin_or_self
from app.models.user import User
from app.schemas.artisan import (
    ArtisanProfileCreate, 
    ArtisanProfileUpdate, 
    ArtisanOut,
    ArtisanLocationUpdate,
    NearbyArtisansRequest,
    NearbyArtisansResponse,
    GeolocationRequest,
    GeolocationResponse
)
from app.services.artisan import ArtisanService
from app.services.geolocation import geolocation_service

router = APIRouter(prefix="/artisans")

@router.post("/profile", response_model=ArtisanOut)
async def create_artisan_profile(
    profile_data: ArtisanProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Create artisan profile - artisan only"""
    service = ArtisanService(db)
    
    # Check if artisan profile already exists
    existing = service.get_artisan_by_user_id(current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artisan profile already exists"
        )
    
    artisan = await service.create_artisan_profile(current_user.id, profile_data)
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create artisan profile"
        )
    
    return artisan

@router.put("/profile", response_model=ArtisanOut)
async def update_artisan_profile(
    profile_data: ArtisanProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Update artisan profile - artisan only"""
    service = ArtisanService(db)
    
    # Get current artisan profile
    artisan = service.get_artisan_by_user_id(current_user.id)
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artisan profile not found"
        )
    
    updated_artisan = await service.update_artisan_profile(artisan.id, profile_data)
    if not updated_artisan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update artisan profile"
        )
    
    return updated_artisan

@router.post("/portfolio/add")
def add_portfolio_item(
    portfolio_item: dict,  # You would create a proper PortfolioItem schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Add portfolio item - artisan only"""
    return {
        "message": "Portfolio item added successfully",
        "artisan_id": current_user.id,
        "portfolio_item": portfolio_item
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
        "portfolio_items": []  # Would fetch actual portfolio from DB
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
        "bookings": []  # Would fetch actual bookings from DB
    }

@router.put("/availability")
def update_availability(
    availability_data: dict,  # You would create a proper AvailabilityUpdate schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Update artisan availability - artisan only"""
    return {
        "message": "Availability updated successfully",
        "artisan_id": current_user.id,
        "availability": availability_data
    }

@router.post("/nearby", response_model=NearbyArtisansResponse)
async def find_nearby_artisans(
    request: NearbyArtisansRequest,
    db: Session = Depends(get_db)
):
    """Find nearby artisans - public endpoint"""
    service = ArtisanService(db)
    result = await service.find_nearby_artisans(request)
    return result

@router.post("/geocode", response_model=GeolocationResponse)
async def geocode_address(
    request: GeolocationRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Convert address to coordinates - authenticated users only"""
    geo_result = await geolocation_service.geocode_address(request.address)
    if not geo_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found or geocoding failed"
        )
    return geo_result

@router.put("/location", response_model=ArtisanOut)
async def update_artisan_location(
    location_data: ArtisanLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Update artisan location with optional geocoding - artisan only"""
    service = ArtisanService(db)
    
    # Get current artisan profile
    artisan = service.get_artisan_by_user_id(current_user.id)
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artisan profile not found"
        )
    
    # If only address is provided, geocode it
    if location_data.location and not (location_data.latitude and location_data.longitude):
        updated_artisan = await service.geocode_and_update_location(
            artisan.id, location_data.location
        )
        if not updated_artisan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to geocode address"
            )
        return updated_artisan
    
    # Otherwise, update with provided data
    profile_update = ArtisanProfileUpdate(
        location=location_data.location,
        latitude=location_data.latitude,
        longitude=location_data.longitude
    )
    
    updated_artisan = await service.update_artisan_profile(artisan.id, profile_update)
    if not updated_artisan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location"
        )
    
    return updated_artisan

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
        "profile": {}  # Would fetch artisan profile from DB
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