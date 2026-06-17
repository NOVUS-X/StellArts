from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.models.event_cursor import EventCursor
from app.models.payment import Payment, PaymentStatus
from app.services.soroban_worker import SorobanEventWorker


class MockSCVal:
    def __init__(self, sym_val=None, str_val=None, bytes_val=None):
        self.sym = sym_val.encode() if sym_val else None
        self.bytes = bytes_val.encode() if bytes_val else None


class MockEventTopic:
    def __init__(self, topics):
        self.topic = topics


class MockEventInfo:
    def __init__(self, ledger, topics, value):
        self.id = f"{ledger}-1"
        self.ledger = str(ledger)
        self.topic = topics
        self.value = value


@pytest.fixture
def mock_worker():
    worker = SorobanEventWorker()
    worker.contract_id = "test_contract"
    return worker


def test_cursor_initialization(db: Session, mock_worker: SorobanEventWorker):
    cursor = mock_worker._get_or_create_cursor(db)
    assert cursor.contract_id == "test_contract"
    assert cursor.last_cursor is not None

    # Second time should return same
    cursor2 = mock_worker._get_or_create_cursor(db)
    assert cursor.id == cursor2.id


def test_process_engagement_initialized(db: Session, mock_worker: SorobanEventWorker):
    # Setup test booking
    from uuid import uuid4

    b_id = uuid4()
    booking = Booking(id=b_id, client_id=1, artisan_id=1, service="test")
    db.add(booking)
    db.commit()

    # Create event
    topics = [MockSCVal(sym_val="EngagementInitializedEvent")]
    value = MockSCVal(bytes_val=str(b_id))
    event = MockEventInfo(100, topics, value)

    # Process
    mock_worker._process_single_event(db, event)
    db.refresh(booking)
    assert booking.status == BookingStatus.IN_PROGRESS

    # Test idempotency
    mock_worker._process_single_event(db, event)
    db.refresh(booking)
    assert booking.status == BookingStatus.IN_PROGRESS


def test_process_fund_released(db: Session, mock_worker: SorobanEventWorker):
    from uuid import uuid4

    b_id = uuid4()
    booking = Booking(
        id=b_id,
        client_id=1,
        artisan_id=1,
        service="test",
        status=BookingStatus.IN_PROGRESS,
    )
    payment = Payment(booking_id=b_id, amount=100.0, status=PaymentStatus.HELD)
    db.add(booking)
    db.add(payment)
    db.commit()

    topics = [MockSCVal(sym_val="FundReleasedEvent")]
    value = MockSCVal(bytes_val=str(b_id))
    event = MockEventInfo(101, topics, value)

    mock_worker._process_single_event(db, event)
    db.refresh(booking)
    db.refresh(payment)
    assert booking.status == BookingStatus.COMPLETED
    assert payment.status == PaymentStatus.RELEASED

    # Idempotency
    mock_worker._process_single_event(db, event)
    assert booking.status == BookingStatus.COMPLETED


def test_process_reclaimed(db: Session, mock_worker: SorobanEventWorker):
    from uuid import uuid4

    b_id = uuid4()
    booking = Booking(
        id=b_id,
        client_id=1,
        artisan_id=1,
        service="test",
        status=BookingStatus.IN_PROGRESS,
    )
    payment = Payment(booking_id=b_id, amount=100.0, status=PaymentStatus.HELD)
    db.add(booking)
    db.add(payment)
    db.commit()

    topics = [MockSCVal(sym_val="ReclaimedEvent")]
    value = MockSCVal(bytes_val=str(b_id))
    event = MockEventInfo(102, topics, value)

    mock_worker._process_single_event(db, event)
    db.refresh(booking)
    db.refresh(payment)
    assert booking.status == BookingStatus.CANCELLED
    assert payment.status == PaymentStatus.REFUNDED

    # Idempotency
    mock_worker._process_single_event(db, event)
    assert booking.status == BookingStatus.CANCELLED
