import uuid
from unittest.mock import patch

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.artisan import Artisan
from app.models.booking import Booking
from app.models.user import User


def make_booking_payload(artisan_id: int, booking_id: str = None):
    return {"booking_id": booking_id or str(uuid.uuid4()), "amount": 10.0, "client_public": "GABC..."}


def test_unverified_user_cannot_prepare(client, db_session):
    # Enable enforcement for this test and restore after
    original = settings.REQUIRE_EMAIL_VERIFICATION
    settings.REQUIRE_EMAIL_VERIFICATION = True
    try:
        # create unverified client user
        hashed = get_password_hash("Password1!")
        client_user = User(email="up@example.com", hashed_password=hashed, role="client")
        db_session.add(client_user)
        db_session.commit()
        db_session.refresh(client_user)

        # create artisan and booking
        artisan_user = User(email="artp@example.com", hashed_password=hashed, role="artisan", is_verified=True)
        db_session.add(artisan_user)
        db_session.commit()
        db_session.refresh(artisan_user)

        artisan = Artisan(user_id=artisan_user.id, business_name="A")
        db_session.add(artisan)
        db_session.commit()
        db_session.refresh(artisan)

        # create client profile and booking
        from app.models.client import Client

        client_profile = Client(user_id=client_user.id)
        db_session.add(client_profile)
        db_session.commit()
        db_session.refresh(client_profile)

        booking = Booking(client_id=client_profile.id, artisan_id=artisan.id, service="S", estimated_cost=50)
        db_session.add(booking)
        db_session.commit()
        db_session.refresh(booking)

        token = create_access_token(subject=client_user.id)

        payload = {"booking_id": str(booking.id), "amount": 50.0, "client_public": "GABC"}
        # Ensure prepare_payment is not called for unverified users
        with patch("app.api.v1.endpoints.payments.prepare_payment") as mock_prepare:
            resp = client.post(
                "/api/v1/payments/prepare",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 403
            mock_prepare.assert_not_called()
    finally:
        settings.REQUIRE_EMAIL_VERIFICATION = original


def test_verified_user_can_prepare(client, db_session):
    original = settings.REQUIRE_EMAIL_VERIFICATION
    settings.REQUIRE_EMAIL_VERIFICATION = True
    try:
        # create verified client user
        hashed = get_password_hash("Password1!")
        client_user = User(email="vp@example.com", hashed_password=hashed, role="client", is_verified=True)
        db_session.add(client_user)
        db_session.commit()
        db_session.refresh(client_user)
        # create artisan and booking
        artisan_user = User(email="artv@example.com", hashed_password=hashed, role="artisan", is_verified=True)
        db_session.add(artisan_user)
        db_session.commit()
        db_session.refresh(artisan_user)

        artisan = Artisan(user_id=artisan_user.id, business_name="B")
        db_session.add(artisan)
        db_session.commit()
        db_session.refresh(artisan)

        from app.models.client import Client

        client_profile = Client(user_id=client_user.id)
        db_session.add(client_profile)
        db_session.commit()
        db_session.refresh(client_profile)

        booking = Booking(client_id=client_profile.id, artisan_id=artisan.id, service="S2", estimated_cost=75)
        db_session.add(booking)
        db_session.commit()
        db_session.refresh(booking)

        token = create_access_token(subject=client_user.id)

        payload = {"booking_id": str(booking.id), "amount": 75.0, "client_public": "GABC"}
        # Patch the prepare_payment function to avoid constructing a real Stellar Account
        with patch("app.api.v1.endpoints.payments.prepare_payment") as mock_prepare:
            mock_prepare.return_value = {
                "status": "prepared",
                "unsigned_xdr": "XDR",
                "booking_id": str(booking.id),
                "amount": str(75.0),
            }
            resp = client.post(
                "/api/v1/payments/prepare",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "prepared"
    finally:
        settings.REQUIRE_EMAIL_VERIFICATION = original


def _make_dummy_tx(memo_text: str):
    class DummyOp:
        def __init__(self):
            class Dest:
                account_id = "ESCROW"

            self.destination = Dest()

    class DummyTx:
        def __init__(self):
            self.memo = type("m", (), {"memo_text": memo_text})
            self.operations = [DummyOp()]

    class DummyEnvelope:
        def __init__(self):
            self.transaction = DummyTx()

    return DummyEnvelope()


def test_unverified_user_cannot_submit(client, db_session, monkeypatch):
    original = settings.REQUIRE_EMAIL_VERIFICATION
    settings.REQUIRE_EMAIL_VERIFICATION = True
    try:
        # create unverified client and booking
        hashed = get_password_hash("Password1!")
        client_user = User(email="usub@example.com", hashed_password=hashed, role="client")
        db_session.add(client_user)
        db_session.commit()
        db_session.refresh(client_user)

        artisan_user = User(email="art3@example.com", hashed_password=hashed, role="artisan", is_verified=True)
        db_session.add(artisan_user)
        db_session.commit()
        db_session.refresh(artisan_user)

        artisan = Artisan(user_id=artisan_user.id, business_name="C")
        db_session.add(artisan)
        db_session.commit()
        db_session.refresh(artisan)

        from app.models.client import Client

        client_profile = Client(user_id=client_user.id)
        db_session.add(client_profile)
        db_session.commit()
        db_session.refresh(client_profile)

        booking = Booking(client_id=client_profile.id, artisan_id=artisan.id, service="S3", estimated_cost=20)
        db_session.add(booking)
        db_session.commit()
        db_session.refresh(booking)

        token = create_access_token(subject=client_user.id)

        # Patch TransactionEnvelope parsing to return dummy envelope with memo
        monkeypatch.setattr(
            "app.api.v1.endpoints.payments.TransactionEnvelope.from_xdr",
            lambda xdr, network_passphrase=None: _make_dummy_tx(f"hold-{booking.id}"),
        )

        # Patch submit_signed_payment to ensure it is not called
        with patch("app.api.v1.endpoints.payments.submit_signed_payment") as mock_submit:
            resp = client.post(
                "/api/v1/payments/submit",
                json={"signed_xdr": "XDR"},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 403
            mock_submit.assert_not_called()
    finally:
        settings.REQUIRE_EMAIL_VERIFICATION = original


def test_verified_user_can_submit(client, db_session, monkeypatch):
    original = settings.REQUIRE_EMAIL_VERIFICATION
    settings.REQUIRE_EMAIL_VERIFICATION = True
    try:
        # create verified client and booking
        hashed = get_password_hash("Password1!")
        client_user = User(email="vsub@example.com", hashed_password=hashed, role="client", is_verified=True)
        db_session.add(client_user)
        db_session.commit()
        db_session.refresh(client_user)
        artisan_user = User(email="art4@example.com", hashed_password=hashed, role="artisan", is_verified=True)
        db_session.add(artisan_user)
        db_session.commit()
        db_session.refresh(artisan_user)

        artisan = Artisan(user_id=artisan_user.id, business_name="D")
        db_session.add(artisan)
        db_session.commit()
        db_session.refresh(artisan)

        from app.models.client import Client

        client_profile = Client(user_id=client_user.id)
        db_session.add(client_profile)
        db_session.commit()
        db_session.refresh(client_profile)

        booking = Booking(client_id=client_profile.id, artisan_id=artisan.id, service="S4", estimated_cost=300)
        db_session.add(booking)
        db_session.commit()
        db_session.refresh(booking)

        token = create_access_token(subject=client_user.id)

        # Patch TransactionEnvelope parsing
        monkeypatch.setattr(
            "app.api.v1.endpoints.payments.TransactionEnvelope.from_xdr",
            lambda xdr, network_passphrase=None: _make_dummy_tx(f"hold-{booking.id}"),
        )

        # Patch submit_signed_payment to simulate success
        with patch("app.api.v1.endpoints.payments.submit_signed_payment") as mock_submit:
            mock_submit.return_value = {"status": "success", "payment_id": "1"}
            resp = client.post(
                "/api/v1/payments/submit",
                json={"signed_xdr": "XDR"},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 200
            mock_submit.assert_called_once()
    finally:
        settings.REQUIRE_EMAIL_VERIFICATION = original
