from typing import List

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

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
        MAIL_FROM=(settings.EMAILS_FROM or settings.SMTP_USER or "no-reply@example.com"),
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
