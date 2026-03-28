"""
Scheduling service.

Proposes optimal booking time slots for an artisan by:
1. Syncing calendar events (if connected).
2. Considering confirmed DB bookings.
3. Scoring candidate time windows by travel distance from the artisan's
   last known job location (lower travel = higher score).
4. Filtering any slot that overlaps a busy window (double-booking prevention).
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.artisan import Artisan
from app.models.booking import Booking, BookingStatus
from app.models.calendar import CalendarEvent
from app.schemas.scheduling import SlotSuggestion, SlotSuggestionRequest, SlotSuggestionResponse
from app.services.calendar_sync import calendar_sync_service

logger = logging.getLogger(__name__)

# Working-day window for candidate slots (inclusive start hour, exclusive end)
DAY_START_HOUR = 8
DAY_END_HOUR = 20

# Assumed average urban travel speed in km/h (used for travel time estimates)
URBAN_AVERAGE_SPEED_KMH = 30.0

# Maximum candidate score (used when artisan has no prior location on a given day)
MAX_SCORE = 100.0


class SchedulingService:
    """Proposes ranked booking slots for an artisan on a given day."""

    async def suggest_slots(
        self,
        request: SlotSuggestionRequest,
        artisan: Artisan,
        db: Session,
    ) -> SlotSuggestionResponse:
        """
        Core scheduling algorithm:

        1. Sync Google/Outlook events (best-effort).
        2. Collect busy windows from calendar + DB bookings.
        3. Enumerate candidate start times in 1-hour increments.
        4. For each candidate, check overlap (double-booking guard).
        5. Score based on travel distance from artisan's prior location.
        6. Return sorted suggestions (best first).
        """
        # ── 1. Sync calendar events (best-effort; errors are swallowed) ──────
        try:
            await calendar_sync_service.sync_artisan_events(artisan.id, db)
        except Exception as exc:
            logger.warning("Calendar sync failed for artisan %s: %s", artisan.id, exc)

        # ── 2. Gather busy windows ───────────────────────────────────────────
        preferred_date = request.preferred_date.replace(tzinfo=timezone.utc)
        busy_windows = self._get_all_busy_windows(artisan.id, preferred_date, db)

        # ── 3. Candidate slots ───────────────────────────────────────────────
        duration = timedelta(hours=request.service_duration_hours)
        candidates = self._build_candidate_slots(preferred_date, duration)

        # ── 4 & 5. Filter overlaps and score ────────────────────────────────
        suggestions: list[SlotSuggestion] = []
        for start, end in candidates:
            if self._overlaps_any(start, end, busy_windows):
                continue  # double-booking prevention

            prior_event = self._find_prior_event(artisan.id, start, db)
            travel_km, travel_minutes, prior_loc_desc = self._compute_travel(
                artisan, prior_event, request.client_lat, request.client_lon
            )
            score = self._score(travel_km)

            suggestions.append(
                SlotSuggestion(
                    start_time=start,
                    end_time=end,
                    travel_time_minutes=round(travel_minutes, 1),
                    travel_km=round(travel_km, 2),
                    score=round(score, 2),
                    prior_job_location=prior_loc_desc,
                )
            )

        # Sort best (highest score) first
        suggestions.sort(key=lambda s: s.score, reverse=True)

        return SlotSuggestionResponse(
            artisan_id=artisan.id,
            preferred_date=preferred_date,
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_all_busy_windows(
        self, artisan_id: int, date: datetime, db: Session
    ) -> list[tuple[datetime, datetime]]:
        """Collect busy windows from both calendar events and DB bookings."""
        windows: list[tuple[datetime, datetime]] = []

        # ── Calendar events ──────────────────────────────────────────────────
        windows.extend(calendar_sync_service.get_busy_slots(artisan_id, date, db))

        # ── DB bookings (confirmed or in-progress) ───────────────────────────
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        db_bookings = (
            db.query(Booking)
            .filter(
                Booking.artisan_id == artisan_id,
                Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS]),
                Booking.date >= day_start,
                Booking.date < day_end,
            )
            .all()
        )
        for b in db_bookings:
            if b.date:
                start = b.date.replace(tzinfo=timezone.utc) if b.date.tzinfo is None else b.date
                hours = float(b.estimated_hours or 1.0)
                end = start + timedelta(hours=hours)
                windows.append((start, end))

        return windows

    def _build_candidate_slots(
        self, date: datetime, duration: timedelta
    ) -> list[tuple[datetime, datetime]]:
        """Enumerate start times from DAY_START_HOUR to DAY_END_HOUR in 1-hour steps."""
        slots = []
        day_base = date.replace(hour=0, minute=0, second=0, microsecond=0)
        for hour in range(DAY_START_HOUR, DAY_END_HOUR):
            start = day_base.replace(hour=hour)
            end = start + duration
            if end.hour > DAY_END_HOUR or (end.hour == DAY_END_HOUR and end.minute > 0):
                break
            slots.append((start, end))
        return slots

    @staticmethod
    def _overlaps_any(
        start: datetime, end: datetime, windows: list[tuple[datetime, datetime]]
    ) -> bool:
        """Return True if [start, end) overlaps any window in *windows*."""
        for w_start, w_end in windows:
            if start < w_end and end > w_start:
                return True
        return False

    def _find_prior_event(
        self, artisan_id: int, slot_start: datetime, db: Session
    ) -> CalendarEvent | None:
        """Return the most recent calendar event ending before *slot_start*."""
        return (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.artisan_id == artisan_id,
                CalendarEvent.end_time <= slot_start,
            )
            .order_by(CalendarEvent.end_time.desc())
            .first()
        )

    def _compute_travel(
        self,
        artisan: Artisan,
        prior_event: CalendarEvent | None,
        client_lat: float,
        client_lon: float,
    ) -> tuple[float, float, str | None]:
        """
        Return (distance_km, travel_minutes, description).

        Priority:
         - prior_event with geocoded lat/lon
         - artisan's own home location (latitude/longitude on artisan profile)
         - 0 km if no location data
        """
        from_lat: float | None = None
        from_lon: float | None = None
        prior_loc_desc: str | None = None

        if prior_event and prior_event.latitude and prior_event.longitude:
            try:
                from_lat = float(prior_event.latitude)
                from_lon = float(prior_event.longitude)
                prior_loc_desc = prior_event.location or "Previous job"
            except (TypeError, ValueError):
                pass

        if from_lat is None and artisan.latitude and artisan.longitude:
            from_lat = float(artisan.latitude)
            from_lon = float(artisan.longitude)
            prior_loc_desc = artisan.location or "Artisan base"

        if from_lat is None or from_lon is None:
            return 0.0, 0.0, None

        distance_km = self._haversine(from_lat, from_lon, client_lat, client_lon)
        travel_minutes = (distance_km / URBAN_AVERAGE_SPEED_KMH) * 60.0
        return distance_km, travel_minutes, prior_loc_desc

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine great-circle distance in km."""
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    @staticmethod
    def _score(distance_km: float) -> float:
        """
        Score a slot inversely proportional to travel distance.
        Score = 100 / (1 + distance_km). So 0 km → 100, 99 km → ~1.
        When distance is 0 (no prior location) the score is MAX_SCORE.
        """
        if distance_km == 0.0:
            return MAX_SCORE
        return MAX_SCORE / (1.0 + distance_km)


# Module-level singleton
scheduling_service = SchedulingService()
