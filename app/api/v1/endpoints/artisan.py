from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.user import User
from app.models.artisan import Artisan
from app.core.auth import get_current_active_user, require_artisan, require_admin, require_artisan_or_admin
from app.db.session import get_db

router = APIRouter(prefix="/artisans")

@router.put("/update-profile")
def update_artisan_profile(
    profile_data: dict,  # You would create a proper ArtisanProfileUpdate schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan)
):
    """Update artisan profile - artisan only"""
    # This is a placeholder implementation
    # In a real app, you'd have proper profile update logic
    return {
        "message": "Artisan profile updated successfully",
        "artisan_id": current_user.id,
        "updated_data": profile_data
    }

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

@router.get("/")
def list_artisans(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """List all artisans - public endpoint"""
    # This would typically be public to allow clients to browse artisans
    return {
        "message": "Public artisan listing",
        "artisans": []  # Would fetch artisan profiles from DB
    }

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