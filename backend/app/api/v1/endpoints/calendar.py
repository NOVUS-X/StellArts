"""
Calendar OAuth API endpoints.

Artisan-only routes for connecting/disconnecting Google Calendar and
Microsoft Outlook (read-only) and listing synced events.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import require_artisan, get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.artisan import Artisan
from app.models.calendar import CalendarEvent
from app.models.user import User
from app.schemas.calendar import (
    CalendarConnectRequest,
    CalendarConnectResponse,
    CalendarEventResponse,
    CalendarStatusResponse,
)
from app.services.calendar_oauth import calendar_oauth_service

router = APIRouter(prefix="/calendar")

SUPPORTED_PROVIDERS = {"google", "microsoft"}


def _get_artisan_or_404(db: Session, current_user: User) -> Artisan:
    artisan = db.query(Artisan).filter(Artisan.user_id == current_user.id).first()
    if not artisan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artisan profile not found for current user",
        )
    return artisan


@router.post("/connect", response_model=CalendarConnectResponse)
def connect_calendar(
    body: CalendarConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """
    Initiate read-only OAuth flow for Google Calendar or Microsoft Outlook.

    Returns the provider authorization URL. The client must redirect the user
    to this URL to grant calendar read access.
    """
    if body.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported provider '{body.provider}'. Choose: {sorted(SUPPORTED_PROVIDERS)}",
        )

    artisan = _get_artisan_or_404(db, current_user)

    try:
        if body.provider == "google":
            auth_url = calendar_oauth_service.get_google_auth_url(artisan.id)
        else:
            auth_url = calendar_oauth_service.get_microsoft_auth_url(artisan.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return CalendarConnectResponse(auth_url=auth_url, provider=body.provider)


@router.get("/callback")
def calendar_callback(
    code: str = Query(...),
    state: str = Query(...),
    provider: str = Query(default="google"),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    OAuth callback endpoint.

    The OAuth provider redirects here after the user grants access.
    The ``state`` parameter encodes ``{provider}:{artisan_id}``.
    On success, stores the token and redirects to the frontend dashboard.
    """
    if error:
        redirect_url = f"{settings.FRONTEND_URL}/dashboard?calendar_error={error}"
        return RedirectResponse(url=redirect_url)

    # state = "provider:artisan_id" or just "artisan_id" (Google flow)
    # We accept both formats for robustness.
    resolved_provider = provider
    artisan_id_str = state
    if ":" in state:
        parts = state.split(":", 1)
        resolved_provider = parts[0]
        artisan_id_str = parts[1]

    try:
        artisan_id = int(artisan_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state parameter") from None

    if resolved_provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {resolved_provider}")

    try:
        if resolved_provider == "google":
            calendar_oauth_service.exchange_google_code(code, artisan_id, db)
        else:
            calendar_oauth_service.exchange_microsoft_code(code, artisan_id, db)
    except Exception as exc:
        logger_msg = str(exc)
        redirect_url = (
            f"{settings.FRONTEND_URL}/dashboard"
            f"?calendar_error=token_exchange_failed&detail={logger_msg[:80]}"
        )
        return RedirectResponse(url=redirect_url)

    redirect_url = f"{settings.FRONTEND_URL}/dashboard?calendar_connected={resolved_provider}"
    return RedirectResponse(url=redirect_url)


@router.delete("/disconnect")
def disconnect_calendar(
    provider: str = Query(..., description="Provider to disconnect: 'google' or 'microsoft'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """Revoke and delete the stored calendar token for a provider."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported provider '{provider}'",
        )

    artisan = _get_artisan_or_404(db, current_user)
    deleted = calendar_oauth_service.revoke_token(artisan.id, provider, db)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} calendar connection found",
        )

    return {"message": f"{provider} calendar disconnected successfully"}


@router.get("/events", response_model=list[CalendarEventResponse])
def list_calendar_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
    skip: int = 0,
    limit: int = 50,
):
    """List synced calendar events for the current artisan (cached locally)."""
    artisan = _get_artisan_or_404(db, current_user)

    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.artisan_id == artisan.id)
        .order_by(CalendarEvent.start_time.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return events


@router.get("/status", response_model=CalendarStatusResponse)
def calendar_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_artisan),
):
    """Check which calendar providers are connected and local event count."""
    artisan = _get_artisan_or_404(db, current_user)
    providers = calendar_oauth_service.get_connected_providers(artisan.id, db)
    event_count = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.artisan_id == artisan.id)
        .count()
    )
    return CalendarStatusResponse(
        connected=len(providers) > 0,
        providers=providers,
        event_count=event_count,
    )
