"""
Tests for CalendarSyncService.

All external API calls (Google, Microsoft Graph) are mocked.
Geolocation is also mocked to avoid network calls.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "False")

from app.models.calendar import ArtisanCalendarToken, CalendarEvent  # noqa: E402
from app.services.calendar_sync import CalendarSyncService  # noqa: E402


@pytest.fixture
def sync_service():
    return CalendarSyncService()


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


# ── _parse_dt tests ───────────────────────────────────────────────────────────

class TestParseDt:
    def test_parses_full_iso_string(self, sync_service):
        dt = sync_service._parse_dt("2026-03-28T10:00:00+00:00")
        assert dt.year == 2026
        assert dt.tzinfo is not None

    def test_parses_date_only_string(self, sync_service):
        dt = sync_service._parse_dt("2026-03-28")
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 28

    def test_parses_Z_suffix(self, sync_service):
        dt = sync_service._parse_dt("2026-03-28T12:00:00Z")
        assert dt.tzinfo is not None


# ── get_busy_slots tests ──────────────────────────────────────────────────────

class TestGetBusySlots:
    def test_returns_busy_window_for_day(self, sync_service, db_session):
        event = CalendarEvent(
            id=uuid.uuid4(),
            artisan_id=1,
            provider="google",
            external_id="evt-1",
            title="Meeting",
            start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            is_busy=True,
        )
        db_session.add(event)
        db_session.commit()

        slots = sync_service.get_busy_slots(
            artisan_id=1,
            date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            db=db_session,
        )
        assert len(slots) == 1
        start, end = slots[0]
        assert start.hour == 9
        assert end.hour == 10

    def test_excludes_free_events(self, sync_service, db_session):
        event = CalendarEvent(
            id=uuid.uuid4(),
            artisan_id=2,
            provider="google",
            external_id="evt-free",
            title="Free block",
            start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            is_busy=False,
        )
        db_session.add(event)
        db_session.commit()

        slots = sync_service.get_busy_slots(
            artisan_id=2,
            date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            db=db_session,
        )
        assert len(slots) == 0


# ── sync_artisan_events / upsert tests ────────────────────────────────────────

class TestSyncArtisanEvents:
    @pytest.mark.asyncio
    async def test_sync_inserts_new_events(self, sync_service, db_session):
        """When no events exist, sync inserts new CalendarEvent rows."""
        mock_events = [
            {
                "external_id": "google-evt-001",
                "title": "Client A",
                "start_time": datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
                "end_time": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
                "location": None,
                "is_busy": True,
            }
        ]

        with (
            patch("app.services.calendar_sync.calendar_oauth_service.get_connected_providers", return_value=["google"]),
            patch("app.services.calendar_sync.calendar_oauth_service.get_valid_access_token", return_value="tok"),
            patch.object(sync_service, "_fetch_google_events", new=AsyncMock(return_value=mock_events)),
            patch("app.services.calendar_sync.geolocation_service.geocode_address", new=AsyncMock(return_value=None)),
        ):
            count = await sync_service.sync_artisan_events(artisan_id=1, db=db_session)

        assert count == 1
        stored = db_session.query(CalendarEvent).filter_by(artisan_id=1).first()
        assert stored is not None
        assert stored.external_id == "google-evt-001"

    @pytest.mark.asyncio
    async def test_sync_upserts_existing_events(self, sync_service, db_session):
        """Re-syncing the same external_id updates the row, not inserts a duplicate."""
        existing = CalendarEvent(
            id=uuid.uuid4(),
            artisan_id=3,
            provider="google",
            external_id="evt-dup",
            title="Old Title",
            start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            is_busy=True,
        )
        db_session.add(existing)
        db_session.commit()

        updated_events = [
            {
                "external_id": "evt-dup",
                "title": "Updated Title",
                "start_time": datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
                "end_time": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),  # end changed
                "location": None,
                "is_busy": True,
            }
        ]

        with (
            patch("app.services.calendar_sync.calendar_oauth_service.get_connected_providers", return_value=["google"]),
            patch("app.services.calendar_sync.calendar_oauth_service.get_valid_access_token", return_value="tok"),
            patch.object(sync_service, "_fetch_google_events", new=AsyncMock(return_value=updated_events)),
            patch("app.services.calendar_sync.geolocation_service.geocode_address", new=AsyncMock(return_value=None)),
        ):
            await sync_service.sync_artisan_events(artisan_id=3, db=db_session)

        rows = db_session.query(CalendarEvent).filter_by(artisan_id=3).all()
        assert len(rows) == 1  # still exactly one row
        db_session.refresh(rows[0])
        assert rows[0].title == "Updated Title"
        assert rows[0].end_time.hour == 11
