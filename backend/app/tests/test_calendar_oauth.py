"""
Tests for CalendarOAuthService – Google and Microsoft OAuth flows.

All external OAuth library calls are mocked so no network access is required.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "False")

from app.models.calendar import ArtisanCalendarToken  # noqa: E402 – env must be set first
from app.services.calendar_oauth import CalendarOAuthService  # noqa: E402


@pytest.fixture
def oauth_service():
    return CalendarOAuthService()


@pytest.fixture
def db_session():
    """In-memory SQLite session with calendar tables."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base
    from app.models import calendar as _cal_models  # noqa: F401 – register models

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ── Google tests ─────────────────────────────────────────────────────────────

class TestGetGoogleAuthUrl:
    def test_returns_url_when_credentials_configured(self, oauth_service):
        """get_google_auth_url() returns a non-empty string when credentials are set."""
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?foo=bar", "state123")

        with (
            patch("app.services.calendar_oauth.settings") as mock_settings,
            patch("app.services.calendar_oauth.Flow", mock_flow, create=True),
        ):
            # Patch Flow inside the method's lazy import namespace
            mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
            mock_settings.GOOGLE_CLIENT_SECRET = "test-secret"
            mock_settings.OAUTH_REDIRECT_URI = "http://localhost:8000/api/v1/calendar/callback"

            with patch("google_auth_oauthlib.flow.Flow.from_client_config") as mock_from_config:
                mock_flow_instance = MagicMock()
                mock_flow_instance.authorization_url.return_value = (
                    "https://accounts.google.com/o/oauth2/auth?foo=bar",
                    "state123",
                )
                mock_from_config.return_value = mock_flow_instance

                url = oauth_service.get_google_auth_url(artisan_id=42)

        assert url.startswith("https://")

    def test_raises_when_credentials_missing(self, oauth_service):
        with patch("app.services.calendar_oauth.settings") as mock_settings:
            mock_settings.GOOGLE_CLIENT_ID = None
            mock_settings.GOOGLE_CLIENT_SECRET = None
            with pytest.raises(ValueError, match="Google OAuth credentials not configured"):
                oauth_service.get_google_auth_url(artisan_id=1)


class TestExchangeGoogleCode:
    def test_stores_token_in_db(self, oauth_service, db_session):
        """exchange_google_code() creates an ArtisanCalendarToken row."""
        mock_creds = MagicMock()
        mock_creds.token = "access-token-abc"
        mock_creds.refresh_token = "refresh-token-xyz"
        mock_creds.expiry = datetime(2026, 4, 1, tzinfo=timezone.utc)
        mock_creds.scopes = ["https://www.googleapis.com/auth/calendar.readonly"]

        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds

        with patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=mock_flow_instance):
            with patch("app.services.calendar_oauth.settings") as mock_settings:
                mock_settings.GOOGLE_CLIENT_ID = "cid"
                mock_settings.GOOGLE_CLIENT_SECRET = "csecret"
                mock_settings.OAUTH_REDIRECT_URI = "http://localhost:8000/api/v1/calendar/callback"

                token_row = oauth_service.exchange_google_code("auth-code", artisan_id=5, db=db_session)

        assert token_row is not None
        assert token_row.provider == "google"
        assert token_row.artisan_id == 5
        assert token_row.access_token == "access-token-abc"

        # Also verify DB row persisted
        from_db = db_session.query(ArtisanCalendarToken).filter_by(artisan_id=5).first()
        assert from_db is not None
        assert from_db.refresh_token == "refresh-token-xyz"


# ── Microsoft tests ───────────────────────────────────────────────────────────

class TestGetMicrosoftAuthUrl:
    def test_returns_url_when_credentials_configured(self, oauth_service):
        mock_msal_app = MagicMock()
        mock_msal_app.get_authorization_request_url.return_value = (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=x"
        )

        with (
            patch("msal.ConfidentialClientApplication", return_value=mock_msal_app),
            patch("app.services.calendar_oauth.settings") as mock_settings,
        ):
            mock_settings.MICROSOFT_CLIENT_ID = "ms-client-id"
            mock_settings.MICROSOFT_CLIENT_SECRET = "ms-secret"
            mock_settings.OAUTH_REDIRECT_URI = "http://localhost:8000/api/v1/calendar/callback"

            url = oauth_service.get_microsoft_auth_url(artisan_id=7)

        assert "microsoftonline.com" in url or url.startswith("https://")

    def test_raises_when_credentials_missing(self, oauth_service):
        with patch("app.services.calendar_oauth.settings") as mock_settings:
            mock_settings.MICROSOFT_CLIENT_ID = None
            mock_settings.MICROSOFT_CLIENT_SECRET = None
            with pytest.raises(ValueError, match="Microsoft OAuth credentials not configured"):
                oauth_service.get_microsoft_auth_url(artisan_id=1)


# ── Revoke / disconnect tests ─────────────────────────────────────────────────

class TestRevokeToken:
    def test_deletes_token_row(self, oauth_service, db_session):
        """revoke_token() removes the token row and returns True."""
        row = ArtisanCalendarToken(
            artisan_id=10,
            provider="google",
            access_token="tok",
            refresh_token="ref",
        )
        db_session.add(row)
        db_session.commit()

        result = oauth_service.revoke_token(artisan_id=10, provider="google", db=db_session)
        assert result is True

        remaining = db_session.query(ArtisanCalendarToken).filter_by(artisan_id=10).first()
        assert remaining is None

    def test_returns_false_when_not_found(self, oauth_service, db_session):
        result = oauth_service.revoke_token(artisan_id=999, provider="google", db=db_session)
        assert result is False


# ── Token refresh tests ───────────────────────────────────────────────────────

class TestGetValidAccessToken:
    def test_returns_none_when_not_connected(self, oauth_service, db_session):
        token = oauth_service.get_valid_access_token(artisan_id=99, provider="google", db=db_session)
        assert token is None

    def test_returns_token_when_not_expired(self, oauth_service, db_session):
        row = ArtisanCalendarToken(
            artisan_id=20,
            provider="google",
            access_token="valid-token",
            refresh_token="ref",
            token_expiry=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(row)
        db_session.commit()

        token = oauth_service.get_valid_access_token(artisan_id=20, provider="google", db=db_session)
        assert token == "valid-token"

    def test_refreshes_expired_google_token(self, oauth_service, db_session):
        row = ArtisanCalendarToken(
            artisan_id=30,
            provider="google",
            access_token="old-token",
            refresh_token="ref-token",
            token_expiry=datetime(2000, 1, 1, tzinfo=timezone.utc),  # expired
        )
        db_session.add(row)
        db_session.commit()

        with patch.object(oauth_service, "refresh_google_token", return_value="new-token") as mock_refresh:
            token = oauth_service.get_valid_access_token(artisan_id=30, provider="google", db=db_session)

        mock_refresh.assert_called_once()
        assert token == "new-token"
