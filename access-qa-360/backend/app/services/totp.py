"""Six-digit codes from an authenticator app (TOTP, RFC 6238: SHA-1, 30-second steps)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code_at(secret: str, counter: int) -> str:
    digest = hmac.new(base64.b32decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    return f"{(struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def verify(secret: str, code: str, last_counter: int | None, now: float | None = None) -> int | None:
    """
    Returns the time step the code belongs to, or None when it is wrong.
    One step either side is allowed for clocks that are slightly off. A code,
    or an older one, cannot be used twice: its step must be after the last one used.
    """
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6:
        return None
    current = int((now if now is not None else time.time()) // STEP)
    for counter in (current, current - 1, current + 1):
        if (last_counter is None or counter > last_counter) and hmac.compare_digest(code_at(secret, counter), code):
            return counter
    return None


def uri(secret: str, email: str) -> str:
    """What the authenticator app reads from the QR code."""
    return f"otpauth://totp/Wiseflow:{quote(email)}?secret={secret}&issuer=Wiseflow&digits=6&period={STEP}"
