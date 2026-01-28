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
    current_user: User = Depends(require_client),
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
        notes=booking_data.get("notes"),
    )

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return {
        "message": "Booking created successfully",
        "booking_id": new_booking.id,
        "status": new_booking.status.value,
        "created_at": new_booking.created_at,
    }


@router.get("/my-bookings")
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_or_artisan),
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
        "bookings": bookings,
    }


@router.get("/all")
def get_all_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
):
    """Get all bookings - admin only"""
    bookings = db.query(Booking).offset(skip).limit(limit).all()
    return {
        "message": "All bookings retrieved",
        "count": len(bookings),
        "bookings": bookings,
    }


@router.put("/{booking_id}/status")
def update_booking_status(
    booking_id: UUID,
    status_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update booking status - role-based state machine enforcement"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check permissions based on role
    from app.models.artisan import Artisan
    from app.models.client import Client

    # Get the user's associated profile (artisan or client)
    user_artisan = None
    user_client = None
    is_artisan = False
    is_client = False

    if current_user.role == "artisan":
        user_artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
        is_artisan = user_artisan and booking.artisan_id == user_artisan.id
    elif current_user.role == "client":
        user_client = db.query(Client).filter(Client.user_id == current_user.id).first()
        is_client = user_client and booking.client_id == user_client.id

    # Admin bypass - can do any transition
    if current_user.role == "admin":
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
            "new_status": booking.status.value,
        }

    # Validate user is associated with this booking
    if not is_artisan and not is_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this booking",
        )

    # Get the requested new status
    new_status_str = status_data.get("status")
    if not new_status_str:
        raise HTTPException(status_code=400, detail="Status is required")

    try:
        new_status = BookingStatus(new_status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status") from None

    current_status = booking.status

    # State Machine Rules
    # PENDING -> CONFIRMED: Only artisan can perform this transition
    if new_status == BookingStatus.CONFIRMED:
        if current_status != BookingStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm booking from {current_status.value} status",
            )
        if not is_artisan:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the artisan can confirm a booking",
            )

    # CONFIRMED -> COMPLETED: Only client can perform this transition
    elif new_status == BookingStatus.COMPLETED:
        if current_status != BookingStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete booking from {current_status.value} status",
            )
        if not is_client:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the client can mark a booking as completed",
            )

    # Any state -> CANCELLED: Role-based cancellation rules
    elif new_status == BookingStatus.CANCELLED:
        if is_client:
            # Client can cancel only if booking is PENDING
            if current_status != BookingStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Clients can only cancel pending bookings",
                )
        elif is_artisan:
            # Artisan can cancel if booking is PENDING or CONFIRMED
            if current_status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Artisans can only cancel pending or confirmed bookings",
                )

    # Apply the status update
    booking.status = new_status
    db.commit()
    db.refresh(booking)

    return {
        "message": f"Booking {booking_id} status updated",
        "updated_by": current_user.id,
        "new_status": booking.status.value,
    }
