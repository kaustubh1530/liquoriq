"""
services/email_service.py — Async HTML email sender via Gmail SMTP

Single responsibility: take a recipient, subject, and HTML body and send it.
All SMTP credentials come from settings (.env) so nothing is hardcoded.

Why aiosmtplib?
  - Our entire stack is async (FastAPI + asyncpg)
  - aiosmtplib lets us await the email send without blocking the event loop
  - If we used smtplib (sync), sending email would freeze the server for ~1-2s

Gmail setup required in .env:
  SMTP_USER=your-gmail@gmail.com
  SMTP_PASSWORD=xxxx xxxx xxxx xxxx   (Gmail App Password — NOT your real password)
  FROM_EMAIL=your-gmail@gmail.com
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_html_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str = "",
) -> None:
    """
    Send an HTML email (with plain-text fallback) via Gmail SMTP.

    Args:
        to_email:  Recipient email address
        subject:   Email subject line
        html_body: Full HTML content of the email
        text_body: Plain-text fallback (auto-generated if not provided)

    Raises:
        RuntimeError: if SMTP credentials are not configured or sending fails
    """
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError(
            "Email not configured. Set SMTP_USER and SMTP_PASSWORD in .env"
        )

    # Build MIME message (multipart/alternative = HTML + plain text fallback)
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"]    = f"LiquorIQ <{settings.from_email or settings.smtp_user}>"
    message["To"]      = to_email

    # Plain text fallback (shown if email client can't render HTML)
    fallback = text_body or _strip_html(html_body)
    message.attach(MIMEText(fallback, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,   # STARTTLS on port 587
        )
        logger.info("Email sent to %s: %s", to_email, subject)
    except aiosmtplib.SMTPException as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        raise RuntimeError(f"Email delivery failed: {e}") from e


def _strip_html(html: str) -> str:
    """Very basic HTML → plain text for the fallback part."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
