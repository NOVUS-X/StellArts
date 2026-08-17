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


async def send_invoice_email(recipients: list[str], booking_id: str, pdf_bytes: bytes) -> None:
    """Send an email with the invoice PDF attached (async)."""
    subject = f"{settings.PROJECT_NAME} - Invoice for Booking #{str(booking_id)[:8].upper()}"
    body = (
        f"Hello,\n\n"
        f"The escrow payment for booking {booking_id} has been successfully released.\n\n"
        f"Please find your invoice/receipt attached to this email.\n\n"
        f"Thank you for using {settings.PROJECT_NAME}!"
    )

    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="plain",
        attachments=[{
            "file": pdf_bytes,
            "filename": f"invoice-{str(booking_id)[:8].upper()}.pdf",
            "mime_type": "application/pdf",
        }]
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
