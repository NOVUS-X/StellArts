from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_active_user,
    require_admin,
    require_client,
    require_client_or_artisan,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.artisan import Artisan
from app.models.booking import Booking, BookingStatus
from app.models.client import Client
from app.models.user import User
from app.schemas.booking import (
    BidCreate,
    BookingCreate,
    BookingResponse,
    BookingStatusUpdate,
)

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
    # Require verified email before creating bookings (configurable)
    if settings.REQUIRE_EMAIL_VERIFICATION and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Email verification required before creating a booking. "
                "Check your inbox or request a new verification email."
            ),
        )
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
    if hasattr(artisan, "is_active") and not artisan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book with an inactive artisan",
        )

    # Use AIService for dynamic bid range calculation and smart pitching
    from app.services.ai_service import ai_service

    # Get artisan's hourly rate (default to 50 if not set)
    hourly_rate = artisan.hourly_rate or Decimal("50.00")
    estimated_hours = (
        booking_data.estimated_hours or 2.0
    )  # Default to 2 hours if not provided

    bid_data = ai_service.calculate_bid_range(
        booking_data.service, hourly_rate, estimated_hours
    )

    pitch = ai_service.generate_smart_pitch(
        booking_data.service,
        bid_data["material_cost"],
        bid_data["labor_cost"],
        bid_data["total_estimated"],
        estimated_hours,
    )

    # Create the booking model instance with status = PENDING
    new_booking = Booking(
        client_id=client.id,
        artisan_id=booking_data.artisan_id,
        service=booking_data.service,
        estimated_hours=estimated_hours,
        estimated_cost=bid_data["total_estimated"],
        labor_cost=bid_data["labor_cost"],
        material_cost=bid_data["material_cost"],
        range_min=bid_data["range_min"],
        range_max=bid_data["range_max"],
        artisan_pitch=pitch,
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
        # Query bookings where the current user is the client
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if client:
            bookings = (
                db.query(Booking)
                .filter(Booking.client_id == client.id)
                .order_by(Booking.created_at.desc())
                .all()
            )

    elif current_user.role == "artisan":
        # Query bookings where the current user is the artisan
        artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
        if artisan:
            bookings = (
                db.query(Booking)
                .filter(Booking.artisan_id == artisan.id)
                .order_by(Booking.created_at.desc())
                .all()
            )

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


@router.put("/{booking_id}/status")
def update_booking_status(
    booking_id: UUID,
    status_payload: BookingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update booking status - role-based state machine enforcement"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found",
        )

    # Get the user's associated profile (artisan or client)
    user_artisan = None
    user_client = None
    is_artisan = False
    is_client = False

    if current_user.role == "artisan":
        user_artisan = (
            db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
        )
        is_artisan = user_artisan and booking.artisan_id == user_artisan.id
    elif current_user.role == "client":
        user_client = db.query(Client).filter(Client.user_id == current_user.id).first()
        is_client = user_client and booking.client_id == user_client.id

    # Admin bypass - can do any transition
    if current_user.role == "admin":
        new_status = status_payload.status
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
            "status": booking.status.value,
        }

    # Validate user is associated with this booking
    if not is_artisan and not is_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this booking",
        )

    # Get the requested new status
    new_status_str = status_payload.status
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

    # CONFIRMED -> IN_PROGRESS: Only artisan can perform this transition
    elif new_status == BookingStatus.IN_PROGRESS:
        if current_status != BookingStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start booking from {current_status.value} status",
            )
        if not is_artisan:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the artisan can start a booking",
            )

    # IN_PROGRESS -> COMPLETED: Only client can perform this transition
    elif new_status == BookingStatus.COMPLETED:
        if current_status != BookingStatus.IN_PROGRESS:
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
            # Artisan can cancel if booking is PENDING, CONFIRMED, or IN_PROGRESS
            if current_status not in (
                BookingStatus.PENDING,
                BookingStatus.CONFIRMED,
                BookingStatus.IN_PROGRESS,
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Artisans can only cancel pending, confirmed, or in-progress bookings",
                )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition to {new_status.value}",
        )

    # Apply the status update
    booking.status = new_status
    db.commit()
    db.refresh(booking)

    return {
        "message": f"Booking {booking_id} status updated",
        "updated_by": current_user.id,
        "new_status": booking.status.value,
        "status": booking.status.value,
    }


@router.post("/{booking_id}/bid")
def submit_bid(
    booking_id: UUID,
    bid_data: BidCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_or_artisan),
):
    """
    Submit a counter-offer (bid) for a booking - artisan only.
    Enforces agentic guardrails: if bid > 300% of range_max, a justification is required.
    """
    if current_user.role != "artisan":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only artisans can submit bids",
        )

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
    if not artisan or booking.artisan_id != artisan.id:
        raise HTTPException(
            status_code=403,
            detail="You are not the assigned artisan for this booking",
        )

    # Enforce Guardrail
    from app.services.ai_service import ai_service

    is_outlier = ai_service.check_guardrail(
        Decimal(str(bid_data.bid_amount)), booking.range_max or Decimal("0")
    )

    if is_outlier and not bid_data.justification:
        return {
            "status": "flagged",
            "message": "AI Alert: Your bid is >300% of the calculated market range. Please provide a justification prompt before showing the user.",
            "requires_justification": True,
        }

    # Update booking with the new bid
    booking.estimated_cost = Decimal(str(bid_data.bid_amount))
    if bid_data.justification:
        booking.notes = (
            booking.notes or ""
        ) + f"\n[Artisan Justification]: {bid_data.justification}"

    db.commit()
    db.refresh(booking)

    return {
        "status": "success",
        "message": "Bid submitted successfully",
        "new_estimated_cost": float(booking.estimated_cost),
    }
