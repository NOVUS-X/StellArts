from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.core.security import get_password_hash
from app.models.artisan import Artisan
from app.models.booking import Booking
from app.models.client import Client
from app.models.payment import Payment, PaymentStatus
from app.models.user import User


def _seed_booking_with_held_payment(db_session):
    hashed = get_password_hash("Password1!")

    client_user = User(
        email="oracle-client@example.com",
        hashed_password=hashed,
        role="client",
        is_verified=True,
        full_name="Client Oracle",
    )
    artisan_user = User(
        email="oracle-artisan@example.com",
        hashed_password=hashed,
        role="artisan",
        is_verified=True,
    )
    db_session.add_all([client_user, artisan_user])
    db_session.commit()
    db_session.refresh(client_user)
    db_session.refresh(artisan_user)

    client_profile = Client(user_id=client_user.id)
    artisan_profile = Artisan(user_id=artisan_user.id, business_name="Oracle Artisan")
    db_session.add_all([client_profile, artisan_profile])
    db_session.commit()
    db_session.refresh(client_profile)
    db_session.refresh(artisan_profile)

    booking = Booking(
        client_id=client_profile.id,
        artisan_id=artisan_profile.id,
        service="Inspection-backed release",
        estimated_cost=Decimal("150.00"),
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    held_payment = Payment(
        booking_id=booking.id,
        amount=Decimal("150.0000000"),
        from_account="GCLIENTHOLD",
        to_account="GESCROWHOLD",
        memo=f"hold-{booking.id}"[:28],
        transaction_hash=f"held-{uuid.uuid4().hex[:10]}",
        status=PaymentStatus.HELD,
    )
    db_session.add(held_payment)
    db_session.commit()

    return booking


def test_oracle_auto_release_triggers_and_notifies(client, db_session):
    booking = _seed_booking_with_held_payment(db_session)

    with (
        patch("app.api.v1.endpoints.payments.settings.BACKEND_ORACLE_TOKEN", "oracle-secret"),
        patch(
            "app.services.payments.release_escrow_via_oracle",
            return_value={
                "success": True,
                "hash": "soroban-hash-123",
                "prepared_xdr": "prepared-xdr",
                "signed_xdr": "signed-xdr",
            },
        ) as mock_release,
        patch(
            "app.api.v1.endpoints.payments.send_auto_release_email",
            new_callable=AsyncMock,
        ) as mock_email,
    ):
        response = client.post(
            "/api/v1/payments/oracle/auto-release",
            headers={"X-Oracle-Token": "oracle-secret"},
            json={
                "booking_id": str(booking.id),
                "engagement_id": 17,
                "token_address": "CDLZFC3SY3TOKEN",
                "confidence_score": 0.96,
                "test_results": {
                    "inspection_suite": "passed",
                    "leak_test": "passed",
                    "beam_alignment": "stable",
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["auto_released"] is True
    assert payload["transaction_hash"] == "soroban-hash-123"
    assert payload["prepared_xdr"] == "prepared-xdr"
    assert payload["client_notification"]["recipient"] == "oracle-client@example.com"
    mock_release.assert_called_once_with(17, "CDLZFC3SY3TOKEN")
    mock_email.assert_awaited_once()

    released = (
        db_session.query(Payment)
        .filter(
            Payment.booking_id == booking.id,
            Payment.status == PaymentStatus.RELEASED,
        )
        .first()
    )
    assert released is not None
    assert released.transaction_hash == "soroban-hash-123"


def test_oracle_auto_release_skips_below_threshold(client, db_session):
    booking = _seed_booking_with_held_payment(db_session)

    with (
        patch("app.api.v1.endpoints.payments.settings.BACKEND_ORACLE_TOKEN", "oracle-secret"),
        patch("app.services.payments.release_escrow_via_oracle") as mock_release,
    ):
        response = client.post(
            "/api/v1/payments/oracle/auto-release",
            headers={"X-Oracle-Token": "oracle-secret"},
            json={
                "booking_id": str(booking.id),
                "engagement_id": 19,
                "token_address": "CDLZFC3SY3TOKEN",
                "confidence_score": 0.89,
                "test_results": ["visual check passed", "confidence below threshold"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "skipped"
    assert payload["auto_released"] is False
    mock_release.assert_not_called()


def test_oracle_auto_release_requires_valid_token(client, db_session):
    booking = _seed_booking_with_held_payment(db_session)

    with patch("app.api.v1.endpoints.payments.settings.BACKEND_ORACLE_TOKEN", "oracle-secret"):
        response = client.post(
            "/api/v1/payments/oracle/auto-release",
            headers={"X-Oracle-Token": "wrong-token"},
            json={
                "booking_id": str(booking.id),
                "engagement_id": 21,
                "token_address": "CDLZFC3SY3TOKEN",
                "confidence_score": 0.97,
                "test_results": "oracle result bundle",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid backend oracle token"
