from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.artisan import Artisan
from app.models.booking import Booking, BookingStatus
from app.models.review import Review

router = APIRouter(prefix="/stats")


@router.get("/")
def get_platform_stats(db: Session = Depends(get_db)):
    """Return real-time platform statistics for the landing page.

    Returns the number of active (available) artisans, the count of completed
    bookings, and the average review rating across all reviews.  All values
    come from live database queries -- nothing is hardcoded.
    """
    artisan_count: int = (
        db.query(func.count(Artisan.id))
        .filter(Artisan.is_available == True)  # noqa: E712
        .scalar()
    ) or 0

    completed_bookings: int = (
        db.query(func.count(Booking.id))
        .filter(Booking.status == BookingStatus.COMPLETED)
        .scalar()
    ) or 0

    average_rating = (
        db.query(func.avg(Review.rating)).scalar()
    )

    return {
        "artisan_count": artisan_count,
        "completed_bookings": completed_bookings,
        "average_rating": round(float(average_rating), 1) if average_rating else None,
    }