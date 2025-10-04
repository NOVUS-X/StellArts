import os
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional

from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset
from stellar_sdk.exceptions import BadRequestError, BadResponseError
from sqlalchemy.orm import Session

from app.models.payment import Payment

# Stellar config
HORIZON = os.getenv("STELLAR_HORIZON", "https://horizon-testnet.stellar.org")
NETWORK_PASSPHRASE = (
    Network.TESTNET_NETWORK_PASSPHRASE
    if os.getenv("STELLAR_NETWORK", "testnet") == "testnet"
    else Network.PUBLIC_NETWORK_PASSPHRASE
)
BASE_FEE = int(os.getenv("STELLAR_BASE_FEE", 100))

server = Server(HORIZON)

ESCROW_SECRET = os.getenv("STELLAR_ESCROW_SECRET")
ESCROW_KEYPAIR = Keypair.from_secret(ESCROW_SECRET) if ESCROW_SECRET else None
ESCROW_PUBLIC = os.getenv("STELLAR_ESCROW_PUBLIC") or (
    ESCROW_KEYPAIR.public_key if ESCROW_KEYPAIR else None
)

if not ESCROW_PUBLIC:
    raise RuntimeError("STELLAR_ESCROW_SECRET or STELLAR_ESCROW_PUBLIC must be configured")

MAX_MEMO_LENGTH = 28

# ---------------------------
# Utilities
# ---------------------------

def _sanitize_amount(amount: Decimal) -> str:
    """Ensure Stellar-compatible precision (7 decimal places max)."""
    return str(amount.quantize(Decimal("0.0000001"), rounding=ROUND_DOWN))


def _record_payment(
    db: Session,
    booking_id: str,
    tx_hash: Optional[str],
    status: str,
    amount: Decimal,
    from_acc: str,
    to_acc: str,
    memo: str,
) -> Dict[str, Any]:
    """Insert payment record into DB and commit."""
    payment = Payment(
        booking_id=booking_id,
        transaction_hash=tx_hash, 
        status=status,
        amount=amount,
        from_account=from_acc,
        to_account=to_acc,
        memo=memo,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {
        "status": "success",
        "payment_id": str(payment.id),
        "transaction_hash": tx_hash,
    }


# ---------------------------
# Main actions
# ---------------------------

def hold_payment(db: Session, client_secret: str, booking_id: str, amount: Decimal) -> Dict[str, Any]:
    """
    Client sends a signed transaction to move funds to escrow.
    Idempotency: if booking already has a 'held' payment, return that record.
    """
    existing = (
        db.query(Payment)
        .filter(Payment.booking_id == booking_id, Payment.status == "held")
        .first()
    )
    if existing:
        return {
            "status": "exists",
            "payment_id": str(existing.id),
            "transaction_hash": existing.transaction_hash,
        }

    client_kp = Keypair.from_secret(client_secret)
    client_pub = client_kp.public_key
    client_account = server.load_account(client_pub)

    # memo = f"hold-{booking_id}"
    memo = f"hold-{booking_id}"[:MAX_MEMO_LENGTH]

    tx = (
        TransactionBuilder(
            source_account=client_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=BASE_FEE,
        )
        .add_text_memo(memo)
        .append_payment_op(
            destination=ESCROW_PUBLIC,
            amount=_sanitize_amount(amount),
            asset=Asset.native(),
        )
        .build()
    )
    tx.sign(client_kp)

    try:
        resp = server.submit_transaction(tx)
        tx_hash = resp["hash"]
        return _record_payment(db, booking_id, tx_hash, "held", amount, client_pub, ESCROW_PUBLIC, memo)
    except (BadRequestError, BadResponseError) as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Database error after Stellar success: {e}"}


def release_payment(db: Session, booking_id: str, artisan_public: str, amount: Decimal) -> Dict[str, Any]:
    """Release funds from escrow to artisan."""
    if not ESCROW_KEYPAIR:
        return {"status": "error", "message": "Escrow key not configured"}

    held = (
        db.query(Payment)
        .filter(Payment.booking_id == booking_id, Payment.status == "held")
        .first()
    )
    if not held:
        return {"status": "error", "message": "No held payment for booking or already released/refunded"}

    already_released = (
        db.query(Payment)
        .filter(Payment.booking_id == booking_id, Payment.status == "released")
        .first()
    )
    if already_released:
        return {
            "status": "exists",
            "payment_id": str(already_released.id),
            "transaction_hash": already_released.transaction_hash,
        }

    escrow_account = server.load_account(ESCROW_PUBLIC)
    # memo = f"release-{booking_id}"
    memo = f"release-{booking_id}"[:MAX_MEMO_LENGTH]
    tx = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=BASE_FEE,
        )
        .add_text_memo(memo)
        .append_payment_op(
            destination=artisan_public,
            amount=_sanitize_amount(amount),
            asset=Asset.native(),
        )
        .build()
    )
    tx.sign(ESCROW_KEYPAIR)

    try:
        resp = server.submit_transaction(tx)
        tx_hash = resp["hash"]
        return _record_payment(db, booking_id, tx_hash, "released", amount, ESCROW_PUBLIC, artisan_public, memo)
    except (BadRequestError, BadResponseError) as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Database error after Stellar success: {e}"}


def refund_payment(db: Session, booking_id: str, client_public: str, amount: Decimal) -> Dict[str, Any]:
    """Refund funds from escrow back to client."""
    if not ESCROW_KEYPAIR:
        return {"status": "error", "message": "Escrow key not configured"}

    held = (
        db.query(Payment)
        .filter(Payment.booking_id == booking_id, Payment.status == "held")
        .first()
    )
    if not held:
        return {"status": "error", "message": "No held payment for booking or already released/refunded"}

    already_refunded = (
        db.query(Payment)
        .filter(Payment.booking_id == booking_id, Payment.status == "refunded")
        .first()
    )
    if already_refunded:
        return {
            "status": "exists",
            "payment_id": str(already_refunded.id),
            "transaction_hash": already_refunded.transaction_hash,
        }

    escrow_account = server.load_account(ESCROW_PUBLIC)
    # memo = f"refund-{booking_id}"
    memo = f"refund-{booking_id}"[:MAX_MEMO_LENGTH]

    tx = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=BASE_FEE,
        )
        .add_text_memo(memo)
        .append_payment_op(
            destination=client_public,
            amount=_sanitize_amount(amount),
            asset=Asset.native(),
        )
        .build()
    )
    tx.sign(ESCROW_KEYPAIR)

    try:
        resp = server.submit_transaction(tx)
        tx_hash = resp["hash"]
        return _record_payment(db, booking_id, tx_hash, "refunded", amount, ESCROW_PUBLIC, client_public, memo)
    except (BadRequestError, BadResponseError) as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Database error after Stellar success: {e}"}
