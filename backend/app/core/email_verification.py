import hashlib
import hmac
import time

from app.core.config import settings

TOKEN_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours


def generate_verification_token(user_id: int, email: str) -> str:
    """Generate an HMAC-signed, time-limited verification token."""
    timestamp = int(time.time())
    message = f"{user_id}:{email}:{timestamp}"
    signature = hmac.new(
        settings.SECRET_KEY.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{user_id}:{timestamp}:{signature}"


def verify_verification_token(token: str, email: str) -> int | None:
    """
    Verify token and return user_id if valid, else None.
    Returns None if token is expired, malformed, or signature doesn't match.
    """
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        user_id, timestamp, provided_sig = parts
        timestamp = int(timestamp)

        # Check expiry
        if time.time() - timestamp > TOKEN_EXPIRY_SECONDS:
            return None

        # Recompute expected signature
        message = f"{user_id}:{email}:{timestamp}"
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        return int(user_id)
    except (ValueError, AttributeError):
        return None
