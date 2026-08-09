"""Outbound email for verification and password reset."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import requests

from backend.config import settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Raised when mail cannot be sent and DEBUG log fallback is unavailable."""


def send_email(*, to_email: str, subject: str, text_body: str) -> None:
    """Send email via Resend, SMTP, or DEBUG log."""

    if settings.resend_api_key.strip():
        _send_resend(to_email=to_email, subject=subject, text_body=text_body)
        return
    if settings.smtp_host.strip():
        _send_smtp(to_email=to_email, subject=subject, text_body=text_body)
        return
    if settings.debug:
        logger.warning(
            "EMAIL (DEBUG, not sent) to=%s subject=%s\n%s",
            to_email,
            subject,
            text_body,
        )
        return
    raise EmailServiceError(
        "Email is not configured. Set RESEND_API_KEY or SMTP_HOST "
        "(or DEBUG=True to log links locally)."
    )


def send_verification_email(*, to_email: str, username: str, link: str) -> None:
    subject = "Verify your ETOZ email"
    body = (
        f"Hi {username},\n\n"
        "Thanks for registering with ETOZ. Verify your email to activate "
        "your account:\n\n"
        f"{link}\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )
    send_email(to_email=to_email, subject=subject, text_body=body)


def send_password_reset_email(*, to_email: str, username: str, link: str) -> None:
    subject = "Reset your ETOZ password"
    body = (
        f"Hi {username},\n\n"
        "We received a request to reset your ETOZ password. "
        "Use this link (expires soon):\n\n"
        f"{link}\n\n"
        "If you did not request a reset, you can ignore this email.\n"
    )
    send_email(to_email=to_email, subject=subject, text_body=body)


def _send_resend(*, to_email: str, subject: str, text_body: str) -> None:
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.strip()}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.email_from,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
        },
        timeout=20,
    )
    if not response.ok:
        raise EmailServiceError(
            f"Resend failed ({response.status_code}): {response.text[:300]}"
        )


def _send_smtp(*, to_email: str, subject: str, text_body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username.strip():
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except Exception as error:  # noqa: BLE001 — surface as service error
        raise EmailServiceError(f"SMTP failed: {error}") from error
