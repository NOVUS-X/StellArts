import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking import Booking, BookingStatus

logger = logging.getLogger(__name__)


class HistoricalDataService:
    """
    Service for calculating price estimates from historical booking data
    """
    
    async def get_historical_estimate(
        self,
        db: Session,
        specialty_tags: list[str],
        location: str,
        min_sample_size: int = None
    ) -> Optional[dict]:
        """
        Calculate price estimate from historical completed bookings
        
        Returns None if insufficient data available
        """
        if min_sample_size is None:
            min_sample_size = settings.HISTORICAL_DATA_MIN_SAMPLE_SIZE
        
        # Query completed bookings with matching specialty tags
        completed_bookings = db.query(Booking).filter(
            Booking.status == BookingStatus.COMPLETED,
            Booking.estimated_cost.isnot(None)
        ).all()
        
        # Filter by specialty tags (fuzzy matching on service description)
        relevant_bookings = []
        for booking in completed_bookings:
            service_lower = booking.service.lower()
            if any(tag.lower() in service_lower for tag in specialty_tags):
                relevant_bookings.append(booking)
        
        if len(relevant_bookings) < min_sample_size:
            logger.info(
                f"Insufficient historical data: {len(relevant_bookings)} bookings "
                f"(minimum: {min_sample_size})"
            )
            return None
        
        # Calculate statistics
        costs = [float(b.estimated_cost) for b in relevant_bookings]
        costs.sort()
        
        # Use 25th and 75th percentiles for range
        p25_index = len(costs) // 4
        p75_index = (3 * len(costs)) // 4
        
        min_price = costs[p25_index]
        max_price = costs[p75_index]
        median_price = costs[len(costs) // 2]
        
        # Confidence based on sample size
        confidence = min(0.75, 0.5 + (len(relevant_bookings) - min_sample_size) * 0.05)
        
        logger.info(
            f"Historical estimate from {len(relevant_bookings)} bookings: "
            f"${min_price:.2f} - ${max_price:.2f} (median: ${median_price:.2f})"
        )
        
        return {
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "confidence": confidence,
            "reasoning": f"Based on {len(relevant_bookings)} similar completed jobs (median: ${median_price:.2f})"
        }


# Global instance
historical_data_service = HistoricalDataService()
