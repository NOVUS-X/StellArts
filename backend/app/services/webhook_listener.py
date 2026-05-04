"""
Webhook Listener Service for Soroban Event Streaming.

This service manages real-time event listening from Soroban smart contracts
using SorobanServer.stream() and processes events to update booking/payment status.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from stellar_sdk import SorobanServer
from stellar_sdk.soroban_rpc import EventFilter

from app.core.config import settings
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.services.event_handler import EventHandler

logger = logging.getLogger(__name__)
class WebhookListenerService:
    """
    Service for listening to Soroban contract events via streaming API.
    
    Features:
    - Redis-based cursor tracking for event processing
    - Event filtering and parsing
    - Retry logic and error handling
    """

    def __init__(
        self,
        server: SorobanServer,
        redis_client: redis.Redis,
        event_handler: EventHandler,
    ):
        self.server = server
        self.redis = redis_client
        self.event_handler = event_handler
        self.contract_address = settings.ESCROW_CONTRACT_ID
        self.stream_timeout = 30
        
    async def start_listening(self) -> None:
        """
        Start listening to contract events.
        """
        if not self.contract_address:
            logger.warning("Contract address not configured")
            return
            
        logger.info(f"Starting webhook listener for contract: {self.contract_address}")
        
        event_filters = [
            EventFilter.event(
                contract_address=self.contract_address,
                topic="EngagementInitializedEvent",
            ),
            EventFilter.event(
                contract_address=self.contract_address,
                topic="ReclaimedEvent",
            ),
        ]
        
        stream = self.server.stream(
            event_filters=event_filters,
            cursor=self._get_cursor(),
        )
        
        try:
            async for envelope in stream:
                await self._process_envelope(envelope)
        except Exception as e:
            logger.error(f"Error in event stream: {e}", exc_info=True)
            raise
            
    async def _process_envelope(self, envelope: Dict[str, Any]) -> None:
        """
        Process a single event envelope from the stream.
        """
        try:
            events = envelope.get("events", [])
            if not events:
                return
                
            for event in events:
                await self._process_event(event)
                
        except Exception as e:
            logger.error(f"Error processing envelope: {e}", exc_info=True)
            
    async def _process_event(self, event: Dict[str, Any]) -> None:
        """
        Process a single event and update database state.
        """
        event_id = event.get("id")
        topic = event.get("topic")
        
        if await self._is_event_processed(event_id):
            logger.debug(f"Skipping already processed event: {event_id}")
            return
            
        logger.info(f"Processing event: {topic} (id: {event_id})")
        
        try:
            await self.event_handler.handle_event(event)
            await self._store_cursor(event_id)
        except Exception as e:
            logger.error(
                f"Error handling event {event_id}: {e}",
                exc_info=True,
            )
            raise
            
    async def _is_event_processed(self, event_id: str) -> bool:
        """
        Check if an event has already been processed.
        """
        cursor_key = f"event_cursor:{event_id}"
        return await self.redis.exists(cursor_key) > 0
        
    async def _store_cursor(self, event_id: str) -> None:
        """
        Store event cursor in Redis to prevent reprocessing.
        """
        cursor_key = f"event_cursor:{event_id}"
        await self.redis.setex(
            cursor_key,
            settings.EVENT_CURSOR_TTL,
            "processed",
        )
        
    def _get_cursor(self) -> Optional[str]:
        """
        Get the last processed cursor from Redis.
        """
        try:
            cursor_key = "webhook_listener:latest_cursor"
            cursor = self.redis.get(cursor_key)
            return cursor.decode("utf-8") if cursor else None
        except Exception as e:
            logger.warning(f"Failed to retrieve cursor: {e}")
            return None
class EventHandler:
    """
    Handles mapping of on-chain events to database state changes.
    """

    async def handle_event(self, event: Dict[str, Any]) -> None:
        """
        Handle an event by mapping it to the appropriate database update.
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
        """
        engagement_id = self._extract_engagement_id(data)
        
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
            await booking.save()
            logger.info(
                f"Booking {booking.id} updated to IN_PROGRESS "
                f"from event engagement_id: {engagement_id}"
            )
            
    async def _handle_reclaimed(self, data: Dict[str, Any]) -> None:
        """
        Handle ReclaimedEvent.
        """
        engagement_id = self._extract_engagement_id(data)
        
        booking = await Booking.query.filter_by(
            booking_id=engagement_id
        ).first()
        
        if booking:
            if booking.status != BookingStatus.PENDING:
                booking.status = BookingStatus.PENDING
                await booking.save()
                logger.info(
                    f"Booking {booking.id} updated to PENDING "
                    f"from event engagement_id: {engagement_id}"
                )
                
        payment = await Payment.query.filter_by(
            booking_id=engagement_id
        ).first()
        
        if payment and payment.status != PaymentStatus.FAILED:
            payment.status = PaymentStatus.FAILED
            await payment.save()
            logger.info(
                f"Payment for booking {engagement_id} marked as FAILED "
                f"from ReclaimedEvent"
            )
            
    def _extract_engagement_id(self, data: Dict[str, Any]) -> int:
        """
        Extract engagement ID from event data.
        """
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
