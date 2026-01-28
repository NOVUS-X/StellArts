from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_active_user,
    require_admin,
    require_client,
    require_client_or_artisan,
)
from app.db.session import get_db
from app.models.booking import Booking, BookingStatus
from app.models.user import User

router = APIRouter(prefix="/bookings")

@router.post("/create")
def create_booking(
    booking_data: dict,  # In a real app, use Pydantic schema
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client)
):
    """Create a new booking - client only"""
    # Find the client profile for the current user
    from app.models.client import Client
    client = db.query(Client).filter(Client.user_id == current_user.id).first()
    if not client:
        # Create a client profile if it doesn't exist (auto-onboarding)
        client = Client(user_id=current_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

    # Validate artisan exists
    from app.models.artisan import Artisan
    artisan_id = booking_data.get("artisan_id")
    artisan = db.query(Artisan).filter(Artisan.id == artisan_id).first()
    if not artisan:
        raise HTTPException(status_code=404, detail="Artisan not found")

    # Create booking
    new_booking = Booking(
        client_id=client.id,
        artisan_id=artisan_id,
        service_description=booking_data.get("service_description"),
        estimated_hours=booking_data.get("estimated_hours"),
        estimated_cost=booking_data.get("estimated_cost"),
        status=BookingStatus.PENDING,
        scheduled_date=datetime.fromisoformat(booking_data.get("scheduled_date")),
        location=booking_data.get("location"),
        notes=booking_data.get("notes")
    )

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return {
        "message": "Booking created successfully",
        "booking_id": new_booking.id,
        "status": new_booking.status.value,
        "created_at": new_booking.created_at
    }

@router.get("/my-bookings")
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_or_artisan)
):
    """Get current user's bookings - clients and artisans only"""
    from app.models.artisan import Artisan
    from app.models.client import Client

    bookings = []

    if current_user.role == "client":
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if client:
            bookings = db.query(Booking).filter(Booking.client_id == client.id).all()

    elif current_user.role == "artisan":
        artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
        if artisan:
            bookings = db.query(Booking).filter(Booking.artisan_id == artisan.id).all()

    return {
        "message": f"Bookings for user {current_user.id}",
        "user_role": current_user.role,
        "bookings": bookings
    }

@router.get("/all")
def get_all_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100
):
    """Get all bookings - admin only"""
    bookings = db.query(Booking).offset(skip).limit(limit).all()
    return {
        "message": "All bookings retrieved",
        "count": len(bookings),
        "bookings": bookings
    }

@router.put("/{booking_id}/status")
def update_booking_status(
    booking_id: UUID,
    status_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update booking status - role-based access control"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check permissions based on role
    from app.models.artisan import Artisan
    from app.models.client import Client

    allowed = False

    if current_user.role == "admin":
        allowed = True
    elif current_user.role == "artisan":
        # Artisan can update bookings assigned to them
        artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
        if artisan and booking.artisan_id == artisan.id:
            allowed = True
    elif current_user.role == "client":
        # Client can only cancel their own bookings
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if client and booking.client_id == client.id:
            if status_data.get("status") == "cancelled":
                allowed = True
            else:
                raise HTTPException(status_code=403, detail="Clients can only cancel bookings")

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update this booking"
        )

    new_status = status_data.get("status")
    if new_status:
        try:
            booking.status = BookingStatus(new_status)
            db.commit()
            db.refresh(booking)
        except ValueError:
             raise HTTPException(status_code=400, detail="Invalid status") from None

    return {
        "message": f"Booking {booking_id} status updated",
        "updated_by": current_user.id,
        "new_status": booking.status.value
    }
