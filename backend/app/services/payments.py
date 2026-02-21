import os
import uuid
from decimal import ROUND_DOWN, Decimal
from typing import Any

from sqlalchemy.orm import Session
from stellar_sdk import (
    Asset,
    Keypair,
    Network,
    Server,
    StrKey,
    TransactionBuilder,
    TransactionEnvelope,
)
from stellar_sdk.exceptions import BadRequestError, BadResponseError

from app.models.booking import Booking
from app.models.payment import Payment, PaymentStatus

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
ESCROW_KEYPAIR = None
ESCROW_PUBLIC = os.getenv("STELLAR_ESCROW_PUBLIC")

if ESCROW_SECRET:
    try:
        ESCROW_KEYPAIR = Keypair.from_secret(ESCROW_SECRET)
        ESCROW_PUBLIC = ESCROW_KEYPAIR.public_key
    except Exception:
        pass  # Invalid secret, will check for public key below

if not ESCROW_PUBLIC or not StrKey.is_valid_ed25519_public_key(ESCROW_PUBLIC):
    # Allow tests to run without strict Stellar configuration.
    import sys

    if "pytest" not in sys.modules:
        raise RuntimeError(
            "STELLAR_ESCROW_SECRET or a valid STELLAR_ESCROW_PUBLIC must be configured"
        )
    else:
        ESCROW_PUBLIC = Keypair.random().public_key

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
    tx_hash: str | None,
    status: str,
    amount: Decimal,
    from_acc: str,
    to_acc: str,
    memo: str,
) -> dict[str, Any]:
    """Insert payment record into DB and commit."""
    booking_uuid = uuid.UUID(booking_id)
    payment = Payment(
        booking_id=booking_uuid,
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


def hold_payment(db: Session, *args, **kwargs) -> dict[str, Any]:
    """DEPRECATED / INSECURE

    The previous implementation accepted a raw Stellar private key from the
    client, built a transaction, and signed it server‑side. This pattern has been
    removed because it violates self‑custody guarantees and exposes client
    funds to server compromise.

    This stub remains only to avoid runtime errors if a caller accidentally
    invokes it; it no longer performs any cryptographic operations.

    Use :func:`prepare_payment` and :func:`submit_signed_payment` instead.  The
    new flow returns an unsigned XDR envelope which is signed in the user's
    wallet, and the backend only ever sees signed XDR.
    """
    return {
        "status": "error",
        "message": (
            "/payments/hold is deprecated. "
            "Use /payments/prepare and /payments/submit with client-side signing."
        ),
    }


def release_payment(
    db: Session, booking_id: str, artisan_public: str, amount: Decimal
) -> dict[str, Any]:
    """Release funds from escrow to artisan."""
    if not ESCROW_KEYPAIR:
        return {"status": "error", "message": "Escrow key not configured"}

    held = (
        db.query(Payment)
        .filter(
            Payment.booking_id == booking_id, Payment.status == PaymentStatus.PENDING
        )
        .first()
    )
    if not held:
        return {
            "status": "error",
            "message": "No held payment for booking or already released/refunded",
        }

    already_released = (
        db.query(Payment)
        .filter(
            Payment.booking_id == booking_id, Payment.status == PaymentStatus.COMPLETED
        )
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
        return _record_payment(
            db,
            booking_id,
            tx_hash,
            PaymentStatus.COMPLETED,
            amount,
            ESCROW_PUBLIC,
            artisan_public,
            memo,
        )
    except (BadRequestError, BadResponseError) as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error after Stellar success: {e}",
        }


def refund_payment(
    db: Session, booking_id: str, client_public: str, amount: Decimal
) -> dict[str, Any]:
    """Refund funds from escrow back to client."""
    if not ESCROW_KEYPAIR:
        return {"status": "error", "message": "Escrow key not configured"}

    held = (
        db.query(Payment)
        .filter(
            Payment.booking_id == booking_id, Payment.status == PaymentStatus.PENDING
        )
        .first()
    )
    if not held:
        return {
            "status": "error",
            "message": "No held payment for booking or already released/refunded",
        }

    already_refunded = (
        db.query(Payment)
        .filter(
            Payment.booking_id == booking_id, Payment.status == PaymentStatus.REFUNDED
        )
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
        return _record_payment(
            db,
            booking_id,
            tx_hash,
            PaymentStatus.REFUNDED,
            amount,
            ESCROW_PUBLIC,
            client_public,
            memo,
        )
    except (BadRequestError, BadResponseError) as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error after Stellar success: {e}",
        }


# ---------------------------------------------------------------------------
# New, secure client-side signing flow (appended automatically)
# ---------------------------------------------------------------------------


def prepare_payment(
    booking_id: str, amount: Decimal, client_public: str
) -> dict[str, Any]:
    """Build an **unsigned** Stellar transaction envelope for a hold.

    The frontend will take the returned XDR, prompt the user via their wallet
    to sign it, and then submit the signed XDR to ``submit_signed_payment``.
    """
    memo = f"hold-{booking_id}"[:MAX_MEMO_LENGTH]
    from stellar_sdk import Account

    source_account = Account(account=client_public, sequence=0)

    tx = (
        TransactionBuilder(
            source_account=source_account,
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

    return {
        "status": "prepared",
        "unsigned_xdr": tx.to_xdr(),
        "booking_id": booking_id,
        "amount": str(amount),
    }


def submit_signed_payment(db: Session, signed_xdr: str) -> dict[str, Any]:
    """Consume a wallet‑signed XDR, perform basic validation, and submit."""
    try:
        tx = TransactionEnvelope.from_xdr(
            signed_xdr, network_passphrase=NETWORK_PASSPHRASE
        )
        assert len(tx.transaction.operations) == 1
        payment_op = tx.transaction.operations[0]
        assert payment_op.destination.account_id == ESCROW_PUBLIC

        resp = server.submit_transaction(tx)
        tx_hash = resp["hash"]
        memo_text = tx.transaction.memo.memo_text
        if isinstance(memo_text, bytes):
            memo_text = memo_text.decode()
        booking_token = memo_text.replace("hold-", "")
        booking_id = booking_token

        try:
            uuid.UUID(booking_id)
        except ValueError:
            candidates = [
                str(row[0])
                for row in db.query(Booking.id).all()
                if str(row[0]).startswith(booking_token)
            ]
            if len(candidates) != 1:
                return {
                    "status": "error",
                    "message": "Unable to resolve booking from transaction memo",
                }
            booking_id = candidates[0]

        return _record_payment(
            db,
            booking_id,
            tx_hash,
            PaymentStatus.PENDING,
            Decimal(payment_op.amount),
            tx.transaction.source.account_id,
            ESCROW_PUBLIC,
            memo_text,
        )
    except AssertionError:
        return {"status": "error", "message": "Transaction structure invalid"}
    except (BadRequestError, BadResponseError) as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Invalid or rejected transaction: {e}"}
