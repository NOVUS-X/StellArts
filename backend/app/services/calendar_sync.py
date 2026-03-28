"""
Calendar sync service.

Fetches calendar events from connected providers (Google / Microsoft) and
caches them locally in the ``calendar_events`` table.  Only free/busy
information is stored – the full event content is never persisted.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.calendar import ArtisanCalendarToken, CalendarEvent
from app.services.calendar_oauth import calendar_oauth_service
from app.services.geolocation import geolocation_service

logger = logging.getLogger(__name__)


class CalendarSyncService:
    """Syncs artisan calendar events from connected providers."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_artisan_events(self, artisan_id: int, db: Session) -> int:
        """
        Fetch events from all connected providers for the next
        ``CALENDAR_SYNC_LOOKAHEAD_DAYS`` days and upsert them into
        ``calendar_events``.

        Returns the total number of events upserted.
        """
        providers = calendar_oauth_service.get_connected_providers(artisan_id, db)
        total = 0
        for provider in providers:
            access_token = calendar_oauth_service.get_valid_access_token(
                artisan_id, provider, db
            )
            if not access_token:
                logger.warning("No valid token for artisan %s / %s", artisan_id, provider)
                continue
            try:
                if provider == "google":
                    events = await self._fetch_google_events(access_token)
                elif provider == "microsoft":
                    events = await self._fetch_microsoft_events(access_token)
                else:
                    continue
                total += await self._upsert_events(artisan_id, provider, events, db)
            except Exception as exc:
                logger.exception("Error syncing %s events for artisan %s: %s", provider, artisan_id, exc)
        return total

    def get_busy_slots(
        self, artisan_id: int, date: datetime, db: Session
    ) -> list[tuple[datetime, datetime]]:
        """
        Return a list of (start, end) busy windows for the given calendar date.
        Only returns ``is_busy=True`` events.
        """
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        events = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.artisan_id == artisan_id,
                CalendarEvent.is_busy.is_(True),
                CalendarEvent.start_time >= day_start,
                CalendarEvent.start_time < day_end,
            )
            .all()
        )
        return [(e.start_time.replace(tzinfo=timezone.utc), e.end_time.replace(tzinfo=timezone.utc)) for e in events]

    def get_events_before_time(
        self, artisan_id: int, before: datetime, db: Session
    ) -> list[CalendarEvent]:
        """Return calendar events that end at or before *before*."""
        ts = before.replace(tzinfo=timezone.utc) if before.tzinfo is None else before
        return (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.artisan_id == artisan_id,
                CalendarEvent.end_time <= ts,
            )
            .order_by(CalendarEvent.end_time.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_google_events(self, access_token: str) -> list[dict]:
        """Call the Google Calendar API and return a normalised list of events."""
        from googleapiclient.discovery import build  # type: ignore[import-untyped]
        from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]

        creds = Credentials(token=access_token)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=settings.CALENDAR_SYNC_LOOKAHEAD_DAYS)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=250,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        raw_events = events_result.get("items", [])
        normalised = []
        for ev in raw_events:
            start_str = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
            end_str = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
            if not start_str or not end_str:
                continue
            normalised.append(
                {
                    "external_id": ev["id"],
                    "title": ev.get("summary"),
                    "start_time": self._parse_dt(start_str),
                    "end_time": self._parse_dt(end_str),
                    "location": ev.get("location"),
                    "is_busy": ev.get("transparency", "opaque") != "transparent",
                }
            )
        return normalised

    async def _fetch_microsoft_events(self, access_token: str) -> list[dict]:
        """Call Microsoft Graph and return a normalised list of events."""
        import aiohttp

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=settings.CALENDAR_SYNC_LOOKAHEAD_DAYS)

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "$select": "id,subject,start,end,location,showAs",
            "startDateTime": now.isoformat(),
            "endDateTime": time_max.isoformat(),
            "$top": 250,
        }

        normalised = []
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://graph.microsoft.com/v1.0/me/calendarView",
                headers=headers,
                params=params,
            ) as resp:
                if resp.status != 200:
                    logger.warning("Microsoft Graph returned %s", resp.status)
                    return []
                data = await resp.json()

        for ev in data.get("value", []):
            start_str = ev.get("start", {}).get("dateTime")
            end_str = ev.get("end", {}).get("dateTime")
            if not start_str or not end_str:
                continue
            normalised.append(
                {
                    "external_id": ev["id"],
                    "title": ev.get("subject"),
                    "start_time": self._parse_dt(start_str),
                    "end_time": self._parse_dt(end_str),
                    "location": ev.get("location", {}).get("displayName"),
                    "is_busy": ev.get("showAs", "busy") not in ("free", "tentative"),
                }
            )
        return normalised

    async def _upsert_events(
        self, artisan_id: int, provider: str, events: list[dict], db: Session
    ) -> int:
        count = 0
        for ev_data in events:
            existing = (
                db.query(CalendarEvent)
                .filter(
                    CalendarEvent.artisan_id == artisan_id,
                    CalendarEvent.provider == provider,
                    CalendarEvent.external_id == ev_data["external_id"],
                )
                .first()
            )

            # Geocode the location if present (best-effort, no error on failure)
            lat_str = lon_str = None
            if ev_data.get("location"):
                geo = await geolocation_service.geocode_address(ev_data["location"])
                if geo:
                    lat_str = str(geo.latitude)
                    lon_str = str(geo.longitude)

            if existing:
                existing.title = ev_data.get("title")
                existing.start_time = ev_data["start_time"]
                existing.end_time = ev_data["end_time"]
                existing.location = ev_data.get("location")
                existing.latitude = lat_str
                existing.longitude = lon_str
                existing.is_busy = ev_data["is_busy"]
                existing.synced_at = datetime.now(timezone.utc)
            else:
                new_event = CalendarEvent(
                    id=uuid.uuid4(),
                    artisan_id=artisan_id,
                    provider=provider,
                    external_id=ev_data["external_id"],
                    title=ev_data.get("title"),
                    start_time=ev_data["start_time"],
                    end_time=ev_data["end_time"],
                    location=ev_data.get("location"),
                    latitude=lat_str,
                    longitude=lon_str,
                    is_busy=ev_data["is_busy"],
                )
                db.add(new_event)
            count += 1

        db.commit()
        return count

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        """Parse ISO-8601 datetime string (with or without timezone)."""
        # Handle date-only strings (all-day events)
        if len(value) == 10:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return datetime.now(timezone.utc)


# Module-level singleton
calendar_sync_service = CalendarSyncService()
