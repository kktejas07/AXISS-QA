"""
Sign in with Google or Microsoft (OpenID Connect, authorization code flow).

The provider confirms who the person is; Wiseflow then signs in the account
with that email address, creating it on first use.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.core.config import settings


class SsoError(Exception):
    """`code` is a short word the sign-in page turns into a message."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


_TENANT = re.compile(r"^[0-9a-fA-F-]{36}$|^[a-z0-9-]+\.onmicrosoft\.com$")


def _microsoft_ready() -> bool:
    # A named tenant is required: with the shared "common" endpoint, the email a
    # Microsoft account reports is not proof that the person owns that address.
    return bool(settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET and _TENANT.match(settings.MICROSOFT_TENANT_ID or ""))


def providers() -> dict[str, bool]:
    return {"google": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET), "microsoft": _microsoft_ready()}


def _config(provider: str) -> dict:
    if provider == "google":
        return {
            "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
            "token": "https://oauth2.googleapis.com/token",
            "userinfo": "https://openidconnect.googleapis.com/v1/userinfo",
            "client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET,
        }
    tenant = settings.MICROSOFT_TENANT_ID
    return {
        "authorize": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "userinfo": "https://graph.microsoft.com/oidc/userinfo",
        "client_id": settings.MICROSOFT_CLIENT_ID, "client_secret": settings.MICROSOFT_CLIENT_SECRET,
    }


def redirect_uri(provider: str) -> str:
    base = (settings.SSO_REDIRECT_BASE or f"{settings.APP_URL.rstrip('/')}/api/v1").rstrip("/")
    return f"{base}/auth/sso/{provider}/callback"


def _sign_state(provider: str, invite: str | None, nonce: str) -> str:
    """Carries the request across the trip to the provider. Signed, and good for ten minutes."""
    claims = {"p": provider, "n": nonce, "use": "sso-state", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}
    if invite:
        claims["i"] = invite
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def read_state(state: str, provider: str, nonce: str | None) -> dict:
    """
    The state must be ours, for this provider, and started in this same browser
    (its nonce matches the cookie set at the start). That last check stops
    someone tricking a person into signing in to an account that is not theirs.
    """
    try:
        claims = jwt.decode(state or "", settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise SsoError("expired")
    if claims.get("use") != "sso-state" or claims.get("p") != provider:
        raise SsoError("expired")
    if not nonce or not secrets.compare_digest(str(claims.get("n", "")), nonce):
        raise SsoError("expired")
    return claims


def authorize_url(provider: str, invite: str | None = None) -> tuple[str, str]:
    """Returns (the provider's sign-in address, the nonce to keep in a cookie until the person comes back)."""
    if not providers().get(provider):
        raise SsoError("unavailable")
    cfg = _config(provider)
    nonce = secrets.token_urlsafe(16)
    return cfg["authorize"] + "?" + urlencode({
        "client_id": cfg["client_id"], "response_type": "code", "scope": "openid email profile",
        "redirect_uri": redirect_uri(provider), "state": _sign_state(provider, invite, nonce), "prompt": "select_account",
    }), nonce


async def identity(provider: str, code: str) -> tuple[str, str]:
    """Swap the provider's code for the person's (email, name). Refuses addresses the provider has not verified."""
    cfg = _config(provider)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await client.post(cfg["token"], data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(provider),
                "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            })
            if token.status_code != 200 or not token.json().get("access_token"):
                raise SsoError("failed")
            info = await client.get(cfg["userinfo"], headers={"Authorization": f"Bearer {token.json()['access_token']}"})
            if info.status_code != 200:
                raise SsoError("failed")
    except (httpx.HTTPError, ValueError):
        raise SsoError("failed")
    data = info.json()
    email = str(data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise SsoError("no_email")
    if provider == "google" and data.get("email_verified") not in (True, "true"):
        raise SsoError("unverified")
    name = str(data.get("name") or "").strip() or email.split("@")[0]
    return email, name[:255]
