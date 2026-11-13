"""Outgoing email over SMTP. With no SMTP_HOST set nothing is sent and callers fall back to shareable links."""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(settings.SMTP_HOST and (settings.SMTP_FROM or settings.SMTP_USER))


def _send(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    if settings.SMTP_PORT == 465:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
    with server:
        if settings.SMTP_PORT != 465:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(message)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send one plain-text email. Returns False, without raising, when email is off or the send fails."""
    if not email_configured():
        return False
    try:
        await asyncio.to_thread(_send, to, subject, body)
        return True
    except Exception as e:  # a mail outage must not break sign-in flows
        log.warning("Email to %s was not sent: %s", to, type(e).__name__)
        return False
