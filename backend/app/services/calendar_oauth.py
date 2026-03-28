"""
Calendar OAuth service.

Handles the read-only OAuth 2.0 flow for Google Calendar and Microsoft Outlook.
Tokens are stored in the ``artisan_calendar_tokens`` table.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.calendar import ArtisanCalendarToken

logger = logging.getLogger(__name__)

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]

MICROSOFT_SCOPES = [
    "https://graph.microsoft.com/Calendars.Read",
    "offline_access",
]


class CalendarOAuthService:
    """Manages OAuth token lifecycle for calendar providers."""

    # ------------------------------------------------------------------
    # Google
    # ------------------------------------------------------------------

    def get_google_auth_url(self, artisan_id: int) -> str:
        """Return Google OAuth2 authorization URL."""
        from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]

        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("Google OAuth credentials not configured")

        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.OAUTH_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            redirect_uri=settings.OAUTH_REDIRECT_URI,
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=str(artisan_id),
            prompt="consent",
        )
        return auth_url

    def exchange_google_code(self, code: str, artisan_id: int, db: Session) -> ArtisanCalendarToken:
        """Exchange Google auth code for tokens and persist them."""
        from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]

        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("Google OAuth credentials not configured")

        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.OAUTH_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            redirect_uri=settings.OAUTH_REDIRECT_URI,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        expiry_dt = credentials.expiry  # already a datetime or None
        if expiry_dt and expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)

        return self._upsert_token(
            db=db,
            artisan_id=artisan_id,
            provider="google",
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_expiry=expiry_dt,
            scope=" ".join(credentials.scopes or []),
        )

    def refresh_google_token(self, token_row: ArtisanCalendarToken, db: Session) -> str:
        """Refresh an expired Google access token in-place and return new access token."""
        from google.auth.transport.requests import Request  # type: ignore[import-untyped]
        from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]

        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("Google OAuth credentials not configured")

        creds = Credentials(
            token=token_row.access_token,
            refresh_token=token_row.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )
        creds.refresh(Request())

        expiry_dt = creds.expiry
        if expiry_dt and expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)

        token_row.access_token = creds.token
        token_row.token_expiry = expiry_dt
        db.commit()
        return creds.token

    # ------------------------------------------------------------------
    # Microsoft
    # ------------------------------------------------------------------

    def get_microsoft_auth_url(self, artisan_id: int) -> str:
        """Return Microsoft OAuth2 authorization URL via MSAL."""
        import msal  # type: ignore[import-untyped]

        if not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET:
            raise ValueError("Microsoft OAuth credentials not configured")

        app = msal.ConfidentialClientApplication(
            settings.MICROSOFT_CLIENT_ID,
            authority="https://login.microsoftonline.com/common",
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
        )
        auth_url = app.get_authorization_request_url(
            scopes=MICROSOFT_SCOPES,
            redirect_uri=settings.OAUTH_REDIRECT_URI,
            state=str(artisan_id),
        )
        return auth_url

    def exchange_microsoft_code(self, code: str, artisan_id: int, db: Session) -> ArtisanCalendarToken:
        """Exchange Microsoft auth code for tokens and persist them."""
        import msal  # type: ignore[import-untyped]

        if not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET:
            raise ValueError("Microsoft OAuth credentials not configured")

        msal_app = msal.ConfidentialClientApplication(
            settings.MICROSOFT_CLIENT_ID,
            authority="https://login.microsoftonline.com/common",
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
        )
        result = msal_app.acquire_token_by_authorization_code(
            code=code,
            scopes=MICROSOFT_SCOPES,
            redirect_uri=settings.OAUTH_REDIRECT_URI,
        )
        if "error" in result:
            raise ValueError(f"Microsoft token exchange failed: {result.get('error_description')}")

        access_token: str = result["access_token"]
        refresh_token: str | None = result.get("refresh_token")

        expires_in: int = result.get("expires_in", 3600)
        expiry_dt = datetime.now(timezone.utc).replace(
            second=datetime.now(timezone.utc).second + expires_in
        )

        return self._upsert_token(
            db=db,
            artisan_id=artisan_id,
            provider="microsoft",
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=expiry_dt,
            scope=" ".join(MICROSOFT_SCOPES),
        )

    def refresh_microsoft_token(self, token_row: ArtisanCalendarToken, db: Session) -> str:
        """Refresh a Microsoft access token using the stored refresh token."""
        import msal  # type: ignore[import-untyped]

        if not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET:
            raise ValueError("Microsoft OAuth credentials not configured")

        msal_app = msal.ConfidentialClientApplication(
            settings.MICROSOFT_CLIENT_ID,
            authority="https://login.microsoftonline.com/common",
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
        )
        result = msal_app.acquire_token_by_refresh_token(
            token_row.refresh_token,
            scopes=MICROSOFT_SCOPES,
        )
        if "error" in result:
            raise ValueError(f"Microsoft token refresh failed: {result.get('error_description')}")

        access_token: str = result["access_token"]
        token_row.access_token = access_token
        db.commit()
        return access_token

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def get_valid_access_token(
        self, artisan_id: int, provider: str, db: Session
    ) -> str | None:
        """Return a valid (refreshed if needed) access token or None if not connected."""
        token_row = (
            db.query(ArtisanCalendarToken)
            .filter(
                ArtisanCalendarToken.artisan_id == artisan_id,
                ArtisanCalendarToken.provider == provider,
            )
            .first()
        )
        if not token_row:
            return None

        now = datetime.now(timezone.utc)
        is_expired = (
            token_row.token_expiry is not None
            and token_row.token_expiry.replace(tzinfo=timezone.utc) <= now
        )

        if is_expired and token_row.refresh_token:
            try:
                if provider == "google":
                    return self.refresh_google_token(token_row, db)
                elif provider == "microsoft":
                    return self.refresh_microsoft_token(token_row, db)
            except Exception as exc:
                logger.warning("Token refresh failed for artisan %s / %s: %s", artisan_id, provider, exc)
                return None

        return token_row.access_token

    def revoke_token(self, artisan_id: int, provider: str, db: Session) -> bool:
        """Delete the stored token for a provider (disconnect)."""
        rows_deleted = (
            db.query(ArtisanCalendarToken)
            .filter(
                ArtisanCalendarToken.artisan_id == artisan_id,
                ArtisanCalendarToken.provider == provider,
            )
            .delete()
        )
        db.commit()
        return rows_deleted > 0

    def get_connected_providers(self, artisan_id: int, db: Session) -> list[str]:
        """Return list of providers the artisan has connected ('google', 'microsoft')."""
        rows = (
            db.query(ArtisanCalendarToken.provider)
            .filter(ArtisanCalendarToken.artisan_id == artisan_id)
            .all()
        )
        return [r.provider for r in rows]

    def _upsert_token(
        self,
        db: Session,
        artisan_id: int,
        provider: str,
        access_token: str,
        refresh_token: str | None,
        token_expiry: datetime | None,
        scope: str | None,
    ) -> ArtisanCalendarToken:
        existing = (
            db.query(ArtisanCalendarToken)
            .filter(
                ArtisanCalendarToken.artisan_id == artisan_id,
                ArtisanCalendarToken.provider == provider,
            )
            .first()
        )
        if existing:
            existing.access_token = access_token
            if refresh_token:
                existing.refresh_token = refresh_token
            existing.token_expiry = token_expiry
            existing.scope = scope
            db.commit()
            db.refresh(existing)
            return existing

        token_row = ArtisanCalendarToken(
            artisan_id=artisan_id,
            provider=provider,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            scope=scope,
        )
        db.add(token_row)
        db.commit()
        db.refresh(token_row)
        return token_row


# Module-level singleton
calendar_oauth_service = CalendarOAuthService()
