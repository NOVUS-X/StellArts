"""
Tests for SchedulingService.

Validates:
- Double-booking prevention (AC #3)
- Geographic grouping scoring (AC #2)
- Graceful operation without calendar connection
- Correct slot enumeration on empty day
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "False")

from app.models.artisan import Artisan  # noqa: E402
from app.models.booking import Booking, BookingStatus  # noqa: E402
from app.models.calendar import CalendarEvent  # noqa: E402
from app.schemas.scheduling import SlotSuggestionRequest  # noqa: E402
from app.services.scheduling import SchedulingService  # noqa: E402


def _make_artisan(artisan_id: int, lat=None, lon=None, location=None):
    """Return a plain-object artisan stub (avoids SQLAlchemy instrumentation)."""
    from types import SimpleNamespace
    from decimal import Decimal
    return SimpleNamespace(
        id=artisan_id,
        latitude=Decimal(str(lat)) if lat is not None else None,
        longitude=Decimal(str(lon)) if lon is not None else None,
        location=location,
    )


@pytest.fixture
def scheduler():
    return SchedulingService()


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base
    from app.models import calendar as _cal_models  # noqa: F401

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def artisan_no_location():
    """Minimal artisan with no lat/lon."""
    return _make_artisan(artisan_id=1)


@pytest.fixture
def artisan_with_location():
    """Artisan based near London (51.5, -0.12)."""
    return _make_artisan(artisan_id=2, lat=51.5074, lon=-0.1278, location="London, UK")


def _make_request(artisan_id: int, date: datetime, duration: float = 2.0) -> SlotSuggestionRequest:
    return SlotSuggestionRequest(
        artisan_id=artisan_id,
        client_lat=51.52,
        client_lon=-0.09,
        service_duration_hours=duration,
        preferred_date=date,
    )


DATE = datetime(2026, 5, 15, tzinfo=timezone.utc)


class TestDoubleBookingPrevention:
    """AC #3: Artisan double-bookings are successfully avoided automatically."""

    @pytest.mark.asyncio
    async def test_calendar_busy_slot_is_excluded(self, scheduler, artisan_no_location, db_session):
        """A slot that overlaps a calendar event must NOT appear in suggestions."""
        # Insert a busy calendar event from 09:00 – 11:00
        event = CalendarEvent(
            id=uuid.uuid4(),
            artisan_id=1,
            provider="google",
            external_id="busy-evt",
            title="Existing job",
            start_time=DATE.replace(hour=9),
            end_time=DATE.replace(hour=11),
            is_busy=True,
        )
        db_session.add(event)
        db_session.commit()

        request = _make_request(artisan_id=1, date=DATE, duration=2.0)

        with patch(
            "app.services.scheduling.calendar_sync_service.sync_artisan_events",
            new=AsyncMock(),
        ):
            result = await scheduler.suggest_slots(request, artisan_no_location, db_session)

        overlapping_starts = [
            s for s in result.suggestions
            if s.start_time.replace(tzinfo=timezone.utc) < DATE.replace(hour=11)
            and s.end_time.replace(tzinfo=timezone.utc) > DATE.replace(hour=9)
        ]
        assert len(overlapping_starts) == 0, (
            f"Expected no overlap with 09:00-11:00 busy block, but got: {overlapping_starts}"
        )

    @pytest.mark.asyncio
    async def test_db_booking_busy_slot_is_excluded(self, scheduler, artisan_no_location, db_session):
        """A slot that overlaps a confirmed DB booking must NOT appear in suggestions."""
        # Insert a minimal booking row using the ORM properly
        booking = Booking(
            client_id=99,
            artisan_id=1,
            status=BookingStatus.CONFIRMED,
            date=DATE.replace(hour=10),
            estimated_hours=2.0,
            service="Test",
            estimated_cost=100.00,
        )
        db_session.add(booking)
        db_session.commit()

        request = _make_request(artisan_id=1, date=DATE, duration=2.0)

        with patch(
            "app.services.scheduling.calendar_sync_service.sync_artisan_events",
            new=AsyncMock(),
        ):
            result = await scheduler.suggest_slots(request, artisan_no_location, db_session)

        # The 10:00-12:00 slot should be excluded
        ten_o_clock_slots = [
            s for s in result.suggestions
            if s.start_time.hour == 10
        ]
        assert len(ten_o_clock_slots) == 0


class TestGeographicGrouping:
    """AC #2: Matching engine prioritises slots that group geographic regions together."""

    @pytest.mark.asyncio
    async def test_nearby_prior_job_scores_higher(self, scheduler, db_session):
        """
        Insert two calendar events ending before the target slots.
        The slot after the event near the client should score higher than the
        slot after the event far away from the client.
        """
        artisan = _make_artisan(artisan_id=5)

        # Near event – is_busy=False so it marks the artisan's LOCATION but doesn't block the 08:00 slot
        near_event = CalendarEvent(
            id=uuid.uuid4(),
            artisan_id=5,
            provider="google",
            external_id="near-evt",
            title="Near job",
            start_time=DATE.replace(hour=6),
            end_time=DATE.replace(hour=8),
            is_busy=False,       # location-only, does NOT block the 08:00 slot
            latitude="51.521",   # very close to client_lat=51.52
            longitude="-0.090",
        )
        # Far event – also is_busy=False, ends at 09:00, location ~343 km from client (London → Paris)
        far_event = CalendarEvent(
            id=uuid.uuid4(),
            artisan_id=5,
            provider="google",
            external_id="far-evt",
            title="Far job",
            start_time=DATE.replace(hour=7),
            end_time=DATE.replace(hour=9),
            is_busy=False,      # location-only, does NOT block the 09:00 slot
            latitude="48.8566",   # Paris
            longitude="2.3522",
        )
        db_session.add(near_event)
        db_session.add(far_event)
        db_session.commit()

        request = _make_request(artisan_id=5, date=DATE, duration=1.0)

        with patch(
            "app.services.scheduling.calendar_sync_service.sync_artisan_events",
            new=AsyncMock(),
        ):
            result = await scheduler.suggest_slots(request, artisan, db_session)

        # Find the slot at 8:00 (right after near_event ends)
        # and at 9:00 (right after far_event ends) – both should be in suggestions
        slots_by_hour = {s.start_time.hour: s for s in result.suggestions}

        assert 8 in slots_by_hour, "Expected a slot at 08:00"
        assert 9 in slots_by_hour, "Expected a slot at 09:00"

        # The 08:00 slot should score higher (travel_km << far slot)
        assert slots_by_hour[8].score > slots_by_hour[9].score, (
            f"Near slot (8:00, km={slots_by_hour[8].travel_km}) should score higher "
            f"than far slot (9:00, km={slots_by_hour[9].travel_km})"
        )


class TestNoCalendarConnected:
    """Scheduling works even when no calendar is connected."""

    @pytest.mark.asyncio
    async def test_returns_suggestions_without_calendar(self, scheduler, artisan_no_location, db_session):
        """When no calendar connection exists, slots are still returned from the DB booking check."""
        request = _make_request(artisan_id=1, date=DATE, duration=1.0)

        with patch(
            "app.services.scheduling.calendar_sync_service.sync_artisan_events",
            new=AsyncMock(),
        ):
            result = await scheduler.suggest_slots(request, artisan_no_location, db_session)

        # With no busy events or bookings, all candidate hours (08-19 for 1h slot) should appear
        assert len(result.suggestions) > 0
        assert result.artisan_id == 1


class TestEmptyDay:
    """On a completely free day, all candidate windows are proposed."""

    @pytest.mark.asyncio
    async def test_full_day_free_returns_all_candidate_slots(self, scheduler, artisan_no_location, db_session):
        request = _make_request(artisan_id=1, date=DATE, duration=1.0)

        with patch(
            "app.services.scheduling.calendar_sync_service.sync_artisan_events",
            new=AsyncMock(),
        ):
            result = await scheduler.suggest_slots(request, artisan_no_location, db_session)

        # 08:00 – 19:00 with 1h slots = 12 candidate windows
        assert len(result.suggestions) == 12


class TestHaversine:
    def test_same_point_zero_distance(self, scheduler):
        assert scheduler._haversine(51.5, -0.12, 51.5, -0.12) == 0.0

    def test_london_to_paris_approximately_340km(self, scheduler):
        dist = scheduler._haversine(51.5074, -0.1278, 48.8566, 2.3522)
        assert 330 < dist < 360, f"Unexpected distance: {dist}"


class TestScoring:
    def test_zero_distance_gives_max_score(self, scheduler):
        assert scheduler._score(0.0) == 100.0

    def test_score_decreases_with_distance(self, scheduler):
        score_near = scheduler._score(1.0)
        score_far = scheduler._score(50.0)
        assert score_near > score_far
