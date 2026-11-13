"""Encrypts third-party credentials (such as a Jira API token) before they are stored."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _cipher() -> Fernet:
    # The key is derived from SECRET_KEY, so changing SECRET_KEY makes stored secrets unreadable.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("wiseflow-secrets:" + settings.SECRET_KEY).encode()).digest()))


def encrypt(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str | None:
    """The original value, or None when it cannot be read (for example after SECRET_KEY changed)."""
    try:
        return _cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return None
