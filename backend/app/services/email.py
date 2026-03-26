from fastapi_mail import ConnectionConfig, FastMail, MessageSchema

from app.core.config import settings


async def send_verification_email(to: str, full_name: str, verify_url: str) -> None:
    """Send a simple verification email (async).

    This uses `fastapi-mail`. In local/dev environments you can point SMTP_HOST
    to Mailhog/MailDev to capture messages.
    """
    subject = f"{settings.PROJECT_NAME} - Verify your email"
    body = (
        f"Hi {full_name},\n\n"
        f"Please verify your email by clicking the link below:\n\n{verify_url}\n\n"
        "If you did not create an account, ignore this message."
    )

    message = MessageSchema(
        subject=subject,
        recipients=[to],
        body=body,
        subtype="plain",
    )

    # Build ConnectionConfig at runtime to avoid strict validation at import time
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USER or "",
        MAIL_PASSWORD=settings.SMTP_PASSWORD or "",
        MAIL_FROM=(
            settings.EMAILS_FROM or settings.SMTP_USER or "no-reply@example.com"
        ),
        MAIL_PORT=settings.SMTP_PORT or 587,
        MAIL_SERVER=settings.SMTP_HOST or "localhost",
        MAIL_STARTTLS=settings.SMTP_TLS,
        MAIL_SSL_TLS=not settings.SMTP_TLS,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
        SUPPRESS_SEND=(settings.SMTP_HOST is None or settings.SMTP_HOST == "localhost"),
    )

    fm = FastMail(conf)
    await fm.send_message(message)


async def send_auto_release_email(
    to: str,
    full_name: str,
    booking_id: str,
    confidence_score: float,
    transaction_hash: str,
    test_results: str,
) -> None:
    """Notify the client that the backend oracle auto-released an escrow."""
    subject = f"{settings.PROJECT_NAME} - Automated milestone release completed"
    body = (
        f"Hi {full_name},\n\n"
        "Your milestone was automatically approved and released because the AI "
        f"confidence score reached {confidence_score:.2f}, above the "
        f"{settings.AUTO_RELEASE_CONFIDENCE_THRESHOLD:.2f} threshold.\n\n"
        f"Booking ID: {booking_id}\n"
        f"Transaction Hash: {transaction_hash}\n\n"
        "Test results:\n"
        f"{test_results}\n\n"
        "No manual approval was required from you for this release."
    )

    message = MessageSchema(
        subject=subject,
        recipients=[to],
        body=body,
        subtype="plain",
    )

    conf = ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USER or "",
        MAIL_PASSWORD=settings.SMTP_PASSWORD or "",
        MAIL_FROM=(
            settings.EMAILS_FROM or settings.SMTP_USER or "no-reply@example.com"
        ),
        MAIL_PORT=settings.SMTP_PORT or 587,
        MAIL_SERVER=settings.SMTP_HOST or "localhost",
        MAIL_STARTTLS=settings.SMTP_TLS,
        MAIL_SSL_TLS=not settings.SMTP_TLS,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
        SUPPRESS_SEND=(settings.SMTP_HOST is None or settings.SMTP_HOST == "localhost"),
    )

    fm = FastMail(conf)
    await fm.send_message(message)
