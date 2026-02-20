from decimal import Decimal

from stellar_sdk import Keypair, TransactionEnvelope, Network

from app.services import payments
from app.models.payment import Payment


def get_auth_headers(client, email, password, role):
    # register & login helper copied from test_crud_endpoints
    client.post(
        "api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": f"Test {role.capitalize()}",
            "phone": "9999999999",
        },
    )
    login_resp = client.post(
        "api/v1/auth/login", json={"email": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_booking(client, artisan_headers, client_headers):
    # create a simple booking so we have an id to work with
    resp = client.post(
        "api/v1/artisans/profile",
        json={"business_name": "Test Artisan", "specialties": ["plumbing"]},
        headers=artisan_headers,
    )
    artisan_id = resp.json()["id"]

    booking_data = {
        "artisan_id": artisan_id,
        "service": "Fix my sink",
        "estimated_hours": 2,
        "estimated_cost": 100.0,
        "date": "2024-12-25T10:00:00",
        "location": "123 Main St",
        "notes": "Urgent",
    }
    resp = client.post(
        "api/v1/bookings/create", json=booking_data, headers=client_headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_payments_prepare_and_submit(monkeypatch, client, db_session):
    # create both roles and booking
    artisan_headers = get_auth_headers(client, "artpay@test.com", "Pass123!", "artisan")
    client_headers = get_auth_headers(client, "clipay@test.com", "Pass123!", "client")

    booking_id = create_booking(client, artisan_headers, client_headers)

    # generate a dummy keypair for the client wallet
    kp = Keypair.random()
    client_pub = kp.public_key

    # patch the server object to avoid outside network calls
    class DummyServer:
        def submit_transaction(self, tx):
            return {"hash": "FAKEHASH"}

    monkeypatch.setattr(payments, "server", DummyServer())

    # 1. prepare
    resp = client.post(
        "api/v1/payments/prepare",
        json={"booking_id": booking_id, "amount": 100.5, "client_public": client_pub},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "prepared"
    unsigned_xdr = payload["unsigned_xdr"]

    # verify we got a valid transaction envelope back
    tx = TransactionEnvelope.from_xdr(unsigned_xdr, network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE)
    assert len(tx.transaction.operations) == 1
    assert tx.transaction.operations[0].destination == payments.ESCROW_PUBLIC

    # sign with our secret
    tx.sign(kp)
    signed_xdr = tx.to_xdr()

    # 2. submit
    resp2 = client.post("api/v1/payments/submit", json={"signed_xdr": signed_xdr})
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["status"] == "success"
    assert body["transaction_hash"] == "FAKEHASH"

    # verify a record was committed to the database
    held = (
        db_session.query(Payment)
        .filter(Payment.booking_id == booking_id, Payment.status == "held")
        .first()
    )
    assert held is not None
    assert held.transaction_hash == "FAKEHASH"


def test_hold_endpoint_removed(client):
    # any call to /payments/hold should 404
    resp = client.post("api/v1/payments/hold", json={})
    assert resp.status_code in (404, 405)
