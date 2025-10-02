from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.models.user import User
from app.models.booking import Booking
from app.core.auth import get_current_active_user, require_client, require_admin, require_client_or_artisan
from app.db.session import get_db

router = APIRouter(prefix="/bookings")

@router.post("/create")
def create_booking(
    booking_data: dict,  # You would create a proper BookingCreate schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client)
):
    """Create a new booking - client only"""
    # This is a placeholder implementation
    # In a real app, you'd have proper booking creation logic
    return {
        "message": "Booking created successfully",
        "user_id": current_user.id,
        "user_role": current_user.role,
        "booking_data": booking_data
    }

@router.get("/my-bookings")
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_or_artisan)
):
    """Get current user's bookings - clients and artisans only"""
    # Placeholder implementation
    return {
        "message": f"Bookings for user {current_user.id}",
        "user_role": current_user.role,
        "bookings": []  # Would fetch actual bookings from DB
    }

@router.get("/all")
def get_all_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100
):
    """Get all bookings - admin only"""
    return {
        "message": "All bookings retrieved",
        "admin_user": current_user.id,
        "bookings": []  # Would fetch all bookings from DB
    }

@router.put("/{booking_id}/status")
def update_booking_status(
    booking_id: int,
    status_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update booking status - role-based access control"""
    # Check permissions based on role
    if current_user.role == "admin":
        # Admin can update any booking
        pass
    elif current_user.role == "artisan":
        # Artisan can update bookings assigned to them
        # In real implementation, check if booking belongs to this artisan
        pass
    elif current_user.role == "client":
        # Client can only cancel their own bookings
        # In real implementation, check if booking belongs to this client
        # and only allow cancellation
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update booking status"
        )
    
    return {
        "message": f"Booking {booking_id} status updated",
        "updated_by": current_user.id,
        "user_role": current_user.role,
        "new_status": status_data
    }