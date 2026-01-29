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
from app.models.artisan import Artisan
from app.models.booking import Booking, BookingStatus
from app.models.client import Client
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponse, BookingStatusUpdate

router = APIRouter(prefix="/bookings")


@router.post(
    "/create", response_model=BookingResponse, status_code=status.HTTP_201_CREATED
)
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """
    Create a new booking - client only

    This endpoint allows clients to create bookings for artisan services.
    The booking is created with PENDING status and requires artisan confirmation.
    """
    # Find or create the client profile for the current user
    from app.models.client import Client

    client = db.query(Client).filter(Client.user_id == current_user.id).first()

    if not client:
        # Auto-onboard: Create a client profile if it doesn't exist
        client = Client(user_id=current_user.id)
        db.add(client)
        db.flush()  # Get the client.id without committing yet

    # Verify that artisan_id exists in the database
    from app.models.artisan import Artisan

    artisan = db.query(Artisan).filter(Artisan.id == booking_data.artisan_id).first()

    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artisan with id {booking_data.artisan_id} not found",
        )

    # Check if artisan is active (optional validation)
    if not artisan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book with an inactive artisan",
        )

    # Create the booking model instance with status = PENDING
    new_booking = Booking(
        client_id=client.id,
        artisan_id=booking_data.artisan_id,
        service=booking_data.service,
        estimated_hours=booking_data.estimated_hours,
        estimated_cost=booking_data.estimated_cost,
        status=BookingStatus.PENDING,
        date=booking_data.date,
        location=booking_data.location,
        notes=booking_data.notes,
    )

    # Add the booking to the session and commit
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return new_booking


@router.get("/my-bookings", response_model=list[BookingResponse])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_or_artisan),
):
    """
    Get current user's bookings - clients and artisans only

    - Clients see bookings they created
    - Artisans see bookings assigned to them
    """
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

    return bookings


@router.get("/all", response_model=list[BookingResponse])
def get_all_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
):
    """Get all bookings - admin only"""
    bookings = db.query(Booking).offset(skip).limit(limit).all()
    return bookings


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific booking by ID

    Access control:
    - Admins can view any booking
    - Clients can view their own bookings
    - Artisans can view bookings assigned to them
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found",
        )

    allowed = False

    if current_user.role == "admin":
        allowed = True
    elif current_user.role == "client":
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if client and booking.client_id == client.id:
            allowed = True
    elif current_user.role == "artisan":
        artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
        if artisan and booking.artisan_id == artisan.id:
            allowed = True

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this booking",
        )

    return booking


def can_update_booking(
    *,
    db: Session,
    booking: Booking,
    user: User,
    new_status: str,
) -> bool:
    if user.role == "admin":
        return True

    if user.role == "artisan":
        artisan = db.query(Artisan).filter(Artisan.user_id == user.id).first()
        return bool(artisan and booking.artisan_id == artisan.id)

    if user.role == "client":
        client = db.query(Client).filter(Client.user_id == user.id).first()
        if client and booking.client_id == client.id:
            return new_status.lower() == "cancelled"

    return False


@router.put("/{booking_id}/status", response_model=BookingResponse)
def update_booking_status(
    booking_id: UUID,
    status_data: BookingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found",
        )

    allowed = can_update_booking(
        db=db,
        booking=booking,
        user=current_user,
        new_status=status_data.status,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update this booking",
        )

    try:
        booking.status = BookingStatus(status_data.status.lower())
        db.commit()
        db.refresh(booking)

    except ValueError as err:
        valid_statuses = [s.value for s in BookingStatus]

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Invalid status. Valid options are: " + ", ".join(valid_statuses)),
        ) from err

    return booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Delete a booking - admin only

    Note: Consider using soft deletes (status update) instead of hard deletes
    for audit trail purposes.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found",
        )

    db.delete(booking)
    db.commit()

    return None
