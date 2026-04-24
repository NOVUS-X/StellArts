import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_client
from app.db.session import get_db
from app.models.booking import Booking, BookingStatus
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewResponse
from app.services.soroban import submit_reputation_on_chain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post(
    "/create",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a review for an artisan",
)
def create_review(
    review_data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """
    Create a review for an artisan after job completion.
    
    This endpoint:
    1. Validates the booking exists and is completed
    2. Verifies the user is the client who made the booking
    3. Checks if a review already exists for this booking
    4. Creates the review in the database
    5. Submits the rating to the on-chain reputation contract
    """
    # 1. Validate booking exists
    booking = db.query(Booking).filter(Booking.id == review_data.booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # 2. Verify the user is the client who made this booking
    if booking.client_id != current_user.client_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review bookings you created",
        )

    # 3. Verify booking is completed
    if booking.status != BookingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can only review completed bookings",
        )

    # 4. Check if review already exists
    existing_review = (
        db.query(Review)
        .filter(Review.booking_id == review_data.booking_id)
        .first()
    )
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A review already exists for this booking",
        )

    # 5. Verify artisan_id matches the booking
    if booking.artisan_id != review_data.artisan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artisan ID does not match the booking",
        )

    # 6. Create the review
    review = Review(
        booking_id=review_data.booking_id,
        client_id=current_user.client_profile.id,
        artisan_id=review_data.artisan_id,
        rating=review_data.rating,
        comment=review_data.comment,
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    # 7. Submit to on-chain reputation contract (non-blocking)
    try:
        # Get artisan's Stellar address from their profile
        artisan_address = booking.artisan.stellar_address if hasattr(booking.artisan, 'stellar_address') else None
        
        if artisan_address:
            submit_reputation_on_chain(
                artisan_address=artisan_address,
                stars=review_data.rating,
            )
            logger.info(
                f"Review {review.id} submitted to on-chain reputation contract "
                f"for artisan {artisan_address}"
            )
        else:
            logger.warning(
                f"Artisan {review_data.artisan_id} has no Stellar address. "
                f"Review {review.id} saved to database only."
            )
    except Exception as e:
        # Log error but don't fail the review creation
        logger.error(
            f"Failed to submit review {review.id} to on-chain contract: {str(e)}"
        )
        # Note: The review is still valid in the database even if on-chain submission fails

    return review


@router.get(
    "/artisan/{artisan_id}",
    response_model=list[ReviewResponse],
    summary="Get all reviews for an artisan",
)
def get_artisan_reviews(
    artisan_id: int,
    db: Session = Depends(get_db),
):
    """Get all reviews for a specific artisan"""
    reviews = (
        db.query(Review)
        .filter(Review.artisan_id == artisan_id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return reviews


@router.get(
    "/booking/{booking_id}",
    response_model=ReviewResponse | None,
    summary="Get review for a specific booking",
)
def get_booking_review(
    booking_id: UUID,
    db: Session = Depends(get_db),
):
    """Get the review for a specific booking (if it exists)"""
    review = (
        db.query(Review)
        .filter(Review.booking_id == booking_id)
        .first()
    )
    return review
