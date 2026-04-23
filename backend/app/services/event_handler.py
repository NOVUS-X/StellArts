"""
Event Handler for mapping on-chain Soroban events to database state.

This service translates emitted contract events into booking/payment
status updates, enforcing the state machine rules.
"""

import logging
from typing import Any, Dict

from app.db.session import db
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus

logger = logging.getLogger(__name__)
class EventHandler:
    """
    Handles mapping of on-chain events to database state changes.
    
    This class contains the business logic for translating Soroban events
    into booking and payment status updates.
    """

    async def handle_event(self, event: Dict[str, Any]) -> None:
        """
        Handle an event by mapping it to the appropriate database update.
        
        Args:
            event: The parsed event data
        """
        topic = event.get("topic")
        data = event.get("data", {})
        
        if topic == "EngagementInitializedEvent":
            await self._handle_engagement_initialized(data)
        elif topic == "ReclaimedEvent":
            await self._handle_reclaimed(data)
        else:
            logger.warning(f"Unhandled event topic: {topic}")
            
    async def _handle_engagement_initialized(self, data: Dict[str, Any]) -> None:
        """
        Handle EngagementInitializedEvent.
        
        This event is emitted when an engagement is initialized on-chain.
        Typically used when an artisan arrives at a job site and confirms
        they've started work.
        
        Args:
            data: Event data dictionary
        """
        engagement_id = self._extract_engagement_id(data)
        
        # Map to Booking IN_PROGRESS state
        booking = await Booking.query.filter_by(
            booking_id=engagement_id
        ).first()
        
        if not booking:
            logger.warning(
                f"No booking found for engagement_id: {engagement_id}"
            )
            return
            
        if booking.status != BookingStatus.IN_PROGRESS:
            booking.status = BookingStatus.IN_PROGRESS
            await db.session.commit()
            await db.session.refresh(booking)
            logger.info(
                f"Booking {booking.id} updated to IN_PROGRESS "
                f"from event engagement_id: {engagement_id}"
            )
            
    async def _handle_reclaimed(self, data: Dict[str, Any]) -> None:
        """
        Handle ReclaimedEvent.
        
        This event is emitted when funds are reclaimed (e.g., when a job
        is cancelled or payment is refused).
        
        Args:
            data: Event data dictionary
        """
        engagement_id = self._extract_engagement_id(data)
        
        # Map booking back to PENDING or update payment status
        booking = await Booking.query.filter_by(
            booking_id=engagement_id
        ).first()
        
        if booking:
            if booking.status != BookingStatus.PENDING:
                booking.status = BookingStatus.PENDING
                await db.session.commit()
                await db.session.refresh(booking)
                logger.info(
                    f"Booking {booking.id} updated to PENDING "
                    f"from event engagement_id: {engagement_id}"
                )
                
        # Also update payment status if payment exists
        payment = await Payment.query.filter_by(
            booking_id=engagement_id
        ).first()
        
        if payment and payment.status != PaymentStatus.FAILED:
            payment.status = PaymentStatus.FAILED
            await db.session.commit()
            await db.session.refresh(payment)
            logger.info(
                f"Payment for booking {engagement_id} marked as FAILED "
                f"from ReclaimedEvent"
            )
            
    def _extract_engagement_id(self, data: Dict[str, Any]) -> int:
        """
        Extract engagement ID from event data.
        
        Args:
            data: Event data dictionary
            
        Returns:
            Engagement ID as integer
        """
        # The exact field name depends on how events are emitted
        # This is a common pattern - check multiple possible field names
        for key in ["engagement_id", "id", "booking_id"]:
            if key in data:
                value = data[key]
                if isinstance(value, int):
                    return value
                try:
                    return int(str(value))
                except (ValueError, TypeError):
                    continue
                    
        logger.error(f"Could not extract engagement_id from event data: {data}")
        raise ValueError("engagement_id not found in event data")
