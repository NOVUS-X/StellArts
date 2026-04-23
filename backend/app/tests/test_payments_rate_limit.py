"""Tests that rate limiting is wired up for payment endpoints."""

from unittest.mock import patch

from app.core import rate_limit as rate_limit_module


def test_limiter_is_attached_to_app():
    """The FastAPI app must expose the slowapi ``Limiter`` as app state."""
    from app.main import app

    assert getattr(app.state, "limiter", None) is rate_limit_module.limiter


def test_payment_endpoints_have_rate_limit_decorator():
    """Each sensitive payment route must be decorated with ``limiter.limit``.

    We check for the ``_rate_limit`` attribute that ``slowapi`` attaches to the
    wrapped function so that the decorator cannot be removed silently.
    """
    from app.api.v1.endpoints import payments

    for name in ("prepare", "submit", "release"):
        fn = getattr(payments, name)
        # slowapi stores the configured limits on the endpoint callable.
        assert hasattr(fn, "_rate_limit") or hasattr(fn, "__wrapped__"), (
            f"payments.{name} is missing a slowapi rate-limit decorator"
        )


def test_failure_limit_triggers_429(client, db_session, monkeypatch):
    """Repeated failed /submit calls should be blocked by the stricter limit."""
    import uuid

    from app.core.security import create_access_token, get_password_hash
    from app.models.artisan import Artisan
    from app.models.booking import Booking
    from app.models.client import Client
    from app.models.user import User

    # Re-enable the limiter just for this test
    original_enabled = rate_limit_module.limiter.enabled
    rate_limit_module.limiter.enabled = True
    # Clear any residual counters
    rate_limit_module.limiter.reset()
    try:
        hashed = get_password_hash("Password1!")
        client_user = User(
            email=f"ratelimit-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hashed,
            role="client",
            is_verified=True,
        )
        db_session.add(client_user)
        db_session.commit()
        db_session.refresh(client_user)

        artisan_user = User(
            email=f"rla-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hashed,
            role="artisan",
            is_verified=True,
        )
        db_session.add(artisan_user)
        db_session.commit()
        db_session.refresh(artisan_user)

        artisan = Artisan(user_id=artisan_user.id, business_name="RL")
        db_session.add(artisan)
        db_session.commit()
        db_session.refresh(artisan)

        client_profile = Client(user_id=client_user.id)
        db_session.add(client_profile)
        db_session.commit()
        db_session.refresh(client_profile)

        booking = Booking(
            client_id=client_profile.id,
            artisan_id=artisan.id,
            service="S",
            estimated_cost=10,
        )
        db_session.add(booking)
        db_session.commit()
        db_session.refresh(booking)

        token = create_access_token(subject=client_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        # Force XDR parsing to always fail so each call hits the failure path
        with patch(
            "app.api.v1.endpoints.payments.TransactionEnvelope.from_xdr",
            side_effect=ValueError("bad xdr"),
        ):
            statuses = []
            # PAYMENT_FAILURE_LIMIT is 3/minute so the 4th call should be 429
            for _ in range(5):
                resp = client.post(
                    "/api/v1/payments/submit",
                    json={"signed_xdr": "BADXDR"},
                    headers=headers,
                )
                statuses.append(resp.status_code)

        assert 429 in statuses, f"expected a 429 in {statuses}"
    finally:
        rate_limit_module.limiter.reset()
        rate_limit_module.limiter.enabled = original_enabled
