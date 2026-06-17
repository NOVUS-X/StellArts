import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session
from stellar_sdk.soroban_rpc import EventFilter, EventFilterType

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.booking import Booking, BookingStatus
from app.models.event_cursor import EventCursor
from app.models.payment import Payment, PaymentStatus
from app.services.soroban import soroban_server

logger = logging.getLogger(__name__)


class SorobanEventWorker:
    def __init__(self):
        self.running = False
        self.poll_interval = 5.0
        self.contract_id = settings.ESCROW_CONTRACT_ID

    async def start(self):
        """Start the background worker loop."""
        if not self.contract_id:
            logger.warning("SorobanEventWorker disabled: ESCROW_CONTRACT_ID not set")
            return

        self.running = True
        logger.info(f"Starting SorobanEventWorker for contract: {self.contract_id}")

        while self.running:
            try:
                await self.process_events()
            except Exception as e:
                logger.error(f"Error in SorobanEventWorker loop: {e}", exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the background worker."""
        logger.info("Stopping SorobanEventWorker...")
        self.running = False

    def _get_or_create_cursor(self, db: Session) -> EventCursor:
        cursor = (
            db.query(EventCursor)
            .filter(EventCursor.contract_id == self.contract_id)
            .with_for_update()
            .first()
        )
        if not cursor:
            # Default to 0, which means starting from the latest in the node,
            # or you could fetch the latest ledger and use that.
            # For this implementation, we use "0" as initial value.
            # In a real scenario, you'd want the ledger sequence where the contract was deployed.
            # Getting latest ledger sequence
            try:
                latest_ledger = soroban_server.get_latest_ledger().sequence
                start_cursor = str(latest_ledger - 1000)  # Give it some buffer
            except Exception:
                start_cursor = "0"

            cursor = EventCursor(contract_id=self.contract_id, last_cursor=start_cursor)
            db.add(cursor)
            db.commit()
            db.refresh(cursor)
        return cursor

    async def process_events(self):
        """Poll and process new events from Soroban."""
        with SessionLocal() as db:
            cursor_record = self._get_or_create_cursor(db)

            try:
                start_ledger = int(cursor_record.last_cursor)
                if start_ledger == 0:
                    try:
                        start_ledger = (
                            soroban_server.get_latest_ledger().sequence - 1000
                        )
                    except Exception:
                        start_ledger = 0
            except ValueError:
                start_ledger = 0

            # If start_ledger is too old, the node might have pruned it.
            # In production, handle "startLedger too old" error by fetching the oldest available.

            event_filter = EventFilter(
                type=EventFilterType.CONTRACT, contract_ids=[self.contract_id]
            )

            try:
                events_response = soroban_server.get_events(
                    start_ledger=start_ledger,
                    filters=[event_filter],
                    pagination={"limit": 100},
                )
            except Exception as e:
                logger.error(f"Failed to fetch events: {e}")
                return

            events = events_response.events

            if not events:
                return

            latest_ledger = start_ledger

            for event in events:
                # We need to ensure we process each event idempotently.
                # event is an EventInfo object
                try:
                    self._process_single_event(db, event)

                    if int(event.ledger) > latest_ledger:
                        latest_ledger = int(event.ledger)
                except Exception as e:
                    logger.error(f"Failed to process event id {event.id}: {e}")
                    # If processing an event fails, we do NOT advance the cursor past it,
                    # ensuring it gets retried on the next loop.
                    # Wait, if we break, we should save the cursor up to the last successful ledger.
                    break

            # Advance cursor if we processed successfully
            if latest_ledger > start_ledger:
                cursor_record.last_cursor = str(latest_ledger)
                db.commit()

    def _process_single_event(self, db: Session, event: Any):
        """
        Process a single Soroban event and update the database idempotently.
        """
        # Event structure is:
        # event.topic is a list of SCVals.
        # event.value is an SCVal.

        if not event.topic or len(event.topic) == 0:
            return

        # The topic is usually an SCVal Symbol
        try:
            topic_val = event.topic[0]
            # Assuming it's a Symbol SCVal, getting the string value
            topic_str = topic_val.sym.decode() if topic_val.sym else ""
        except AttributeError:
            topic_str = ""

        # Extract booking_id (or engagement_id) from the event topics or value.
        # Assuming booking_id is the second topic, or inside the value.
        # For simplicity in this implementation, we will assume it's in the value as a string.
        # And we'll match by the booking_id UUID string.

        # The actual parsing will heavily depend on the exact Rust contract.
        # Here is a generic parsing logic that looks for the string representation:
        booking_id_str = self._extract_booking_id(event)

        if not booking_id_str:
            return

        # Match topics exactly
        # If the user specifically said "EngagementInitializedEvent", "FundReleasedEvent", "ReclaimedEvent"

        if topic_str in ["EngagementInitializedEvent", "EngagementInitialized"]:
            self._handle_engagement_initialized(db, booking_id_str)
        elif topic_str in ["FundReleasedEvent", "FundReleased"]:
            self._handle_fund_released(db, booking_id_str)
        elif topic_str in ["ReclaimedEvent", "Reclaimed"]:
            self._handle_reclaimed(db, booking_id_str)

    def _extract_booking_id(self, event: Any) -> str | None:
        """Extract booking_id from event value or topics."""
        # Simple extraction: iterate through topics and value, try to find a UUID or numeric ID.
        # Let's assume booking_id is passed as the second topic (e.g. `symbol_short!("init"), booking_id`).
        if len(event.topic) > 1:
            try:
                # If booking_id is a string/bytes
                if event.topic[1].bytes:
                    return event.topic[1].bytes.decode()
                # If it's a u64
                if event.topic[1].u64:
                    return str(event.topic[1].u64)
            except AttributeError:
                pass

        # Or maybe it's in the value
        try:
            if event.value.bytes:
                return event.value.bytes.decode()
        except AttributeError:
            pass

        return None

    def _handle_engagement_initialized(self, db: Session, booking_id_str: str):
        # Update booking status to IN_PROGRESS idempotently
        booking = self._get_booking(db, booking_id_str)
        if (
            booking
            and booking.status != BookingStatus.IN_PROGRESS
            and booking.status != BookingStatus.COMPLETED
        ):
            booking.status = BookingStatus.IN_PROGRESS
            db.commit()

    def _handle_fund_released(self, db: Session, booking_id_str: str):
        # Update booking status to COMPLETED and payment to RELEASED idempotently
        booking = self._get_booking(db, booking_id_str)
        if booking and booking.status != BookingStatus.COMPLETED:
            booking.status = BookingStatus.COMPLETED
            db.commit()

        payment = self._get_payment(db, booking_id_str)
        if payment and payment.status != PaymentStatus.RELEASED:
            payment.status = PaymentStatus.RELEASED
            db.commit()

    def _handle_reclaimed(self, db: Session, booking_id_str: str):
        # Update booking to CANCELLED and payment to REFUNDED idempotently
        booking = self._get_booking(db, booking_id_str)
        if booking and booking.status != BookingStatus.CANCELLED:
            booking.status = BookingStatus.CANCELLED
            db.commit()

        payment = self._get_payment(db, booking_id_str)
        if payment and payment.status != PaymentStatus.REFUNDED:
            payment.status = PaymentStatus.REFUNDED
            db.commit()

    def _get_booking(self, db: Session, booking_id_str: str) -> Booking | None:
        # Assuming booking_id_str can be parsed into the UUID format
        # Or if it's an integer engagement_id, we need to query by that.
        # Since the problem statement says "Update the corresponding booking/payment status in PostgreSQL automatically"
        # and "extract the booking_id", we'll query by ID.
        try:
            import uuid

            # Check if it's a UUID string
            b_id = uuid.UUID(booking_id_str)
            return db.query(Booking).filter(Booking.id == b_id).first()
        except ValueError:
            # If it's a numeric ID, we might need a different column or prefix search
            # Here we just fallback to returning None if it's not a valid UUID
            return None

    def _get_payment(self, db: Session, booking_id_str: str) -> Payment | None:
        try:
            import uuid

            b_id = uuid.UUID(booking_id_str)
            return db.query(Payment).filter(Payment.booking_id == b_id).first()
        except ValueError:
            return None


worker = SorobanEventWorker()
