"""
Platform settings a super admin can change from the console.

Every setting here also exists as an environment variable on the server. A value
saved from the console is stored encrypted and replaces the environment value;
removing it puts the environment value back. The rest of the app keeps reading
`settings.X`, so nothing else has to know where a value came from.

With several server processes, a change reaches the others within half a minute
(see `keep_fresh`).
"""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.secrets import decrypt, encrypt
from app.models.platform import PlatformSetting

log = logging.getLogger(__name__)

# group -> (title, what it is for, [(key, label, secret?)])
GROUPS: dict[str, tuple[str, str, list[tuple[str, str, bool]]]] = {
    "ai": ("AI model", "Writes test cases, scripts, summaries and Wise's answers for organisations without their own key.", [
        ("DEFAULT_AI_PROVIDER", "Provider", False),
        ("ANTHROPIC_API_KEY", "Claude (Anthropic) key", True),
        ("DEFAULT_AI_KEY", "Key for another provider", True),
        ("DEFAULT_AI_MODEL", "Model name (optional)", False),
        ("DEFAULT_AI_BASE_URL", "Address, for a custom provider", False),
        ("AI_MONTHLY_CAP_USD", "Monthly allowance per organisation, in US dollars (0 for none)", False),
    ]),
    "embeddings": ("Meaning-based search", "Lets Wise find passages by meaning, not only by matching words.", [
        ("EMBEDDINGS_API_KEY", "Key", True),
        ("EMBEDDINGS_BASE_URL", "Address", False),
        ("EMBEDDINGS_MODEL", "Model name", False),
    ]),
    "google": ("Sign in with Google", "Lets people sign in with their Google account.", [
        ("GOOGLE_CLIENT_ID", "Client ID", False),
        ("GOOGLE_CLIENT_SECRET", "Client secret", True),
    ]),
    "email": ("Email", "Sends invitations, password reset links and scheduled scan results.", [
        ("SMTP_HOST", "Mail server", False),
        ("SMTP_PORT", "Port", False),
        ("SMTP_USER", "User name", False),
        ("SMTP_PASSWORD", "Password", True),
        ("SMTP_FROM", "From address", False),
    ]),
    "stripe": ("Stripe", "Takes card payments in US dollars.", [
        ("STRIPE_SECRET_KEY", "Secret key", True),
        ("STRIPE_WEBHOOK_SECRET", "Webhook signing secret", True),
    ]),
    "razorpay": ("Razorpay", "Takes payments in rupees.", [
        ("RAZORPAY_KEY_ID", "Key ID", False),
        ("RAZORPAY_KEY_SECRET", "Key secret", True),
        ("RAZORPAY_WEBHOOK_SECRET", "Webhook secret", True),
    ]),
}
KEYS: dict[str, tuple[str, str, bool]] = {key: (group, label, secret) for group, (_, _, fields) in GROUPS.items() for key, label, secret in fields}
NUMBERS = {"SMTP_PORT": (1, 65535), "AI_MONTHLY_CAP_USD": (0, 1_000_000)}
ADDRESSES = ("DEFAULT_AI_BASE_URL", "EMBEDDINGS_BASE_URL")

# What the server's environment said when it started, to go back to when a console value is removed.
_ENV = {key: getattr(settings, key) for key in KEYS}
_from_console: set[str] = set()


class SettingError(Exception):
    pass


def clean(key: str, value: str) -> str:
    """The value as it will be stored. Raises SettingError with a sentence the admin can act on."""
    from app.core.providers import PROVIDERS

    value = (value or "").strip()
    if key not in KEYS:
        raise SettingError("That setting cannot be changed here")
    if len(value) > 500 or "\n" in value or "\r" in value:
        raise SettingError("That value is too long or has a line break in it")
    if key in NUMBERS:
        low, high = NUMBERS[key]
        if not value.isdigit() or not low <= int(value) <= high:
            raise SettingError(f"Enter a whole number from {low} to {high}")
    if key == "DEFAULT_AI_PROVIDER" and value not in PROVIDERS:
        raise SettingError("Choose one of the listed providers")
    if key in ADDRESSES:
        from app.services.chatbot_auditor import ChatbotError, check_endpoint

        try:
            check_endpoint(value)
        except ChatbotError:
            raise SettingError("Enter a public address starting with https://")
    return value


def _apply(values: dict[str, str]) -> None:
    for key in KEYS:
        if key in values:
            setattr(settings, key, int(values[key]) if key in NUMBERS else values[key])
        else:
            setattr(settings, key, _ENV[key])
    _from_console.clear()
    _from_console.update(values)


def reset() -> None:
    """Back to the server's environment. Used by tests."""
    _apply({})
    _spend.clear()


async def refresh(db) -> None:
    """Read the console's values and put them in force in this process."""
    rows = (await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_(list(KEYS))))).scalars().all()
    values = {}
    for row in rows:
        value = decrypt(row.value_encrypted)
        if value is None:
            log.warning("Platform setting %s cannot be read (SECRET_KEY changed?); the server's own value is used", row.key)
        elif value != "":
            values[row.key] = value
    _apply(values)


_read_at = 0.0


def refresh_sync() -> None:
    """The same for background workers, which have no event loop. At most once a minute; never raises."""
    global _read_at
    if time.monotonic() - _read_at < 60:
        return
    _read_at = time.monotonic()
    from app.core.ai import _engine

    try:
        with _engine().connect() as db:
            rows = db.execute(select(PlatformSetting.key, PlatformSetting.value_encrypted).where(PlatformSetting.key.in_(list(KEYS)))).all()
        values = {key: decrypt(value) for key, value in rows}
        _apply({key: value for key, value in values.items() if value})
    except Exception as e:
        log.debug("Platform settings were not refreshed: %s", type(e).__name__)


async def keep_fresh() -> None:
    """So a change made through one server process reaches the others."""
    from app.core.database import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await refresh(db)
        except Exception as e:  # the database being away must not stop the server
            log.debug("Platform settings were not refreshed: %s", type(e).__name__)
        await asyncio.sleep(30)


async def save(db, values: dict[str, str], user_id: str | None) -> list[tuple[str, str]]:
    """Store cleaned values ("" removes one). Returns (key, what happened) for the audit log; never the value."""
    done = []
    for key, value in values.items():
        row = await db.get(PlatformSetting, key)
        if value == "":
            if row:
                await db.delete(row)
                done.append((key, "removed; the server's own value applies again"))
        elif row:
            if decrypt(row.value_encrypted) != value:
                row.value_encrypted, row.updated_by = encrypt(value), user_id
                done.append((key, "replaced"))
        else:
            db.add(PlatformSetting(key=key, value_encrypted=encrypt(value), updated_by=user_id))
            done.append((key, "set"))
    await db.flush()
    await refresh(db)
    return done


def _shown(key: str) -> dict:
    group, label, secret = KEYS[key]
    value = str(getattr(settings, key) or "")
    if key == "AI_MONTHLY_CAP_USD" and value == "0":
        value = ""
    out = {"key": key, "label": label, "secret": secret, "set": bool(value),
           "source": ("console" if key in _from_console else "server") if value else None}
    if secret:
        # Enough to tell two keys apart, never enough to use one.
        out["hint"] = f"ends in {value[-4:]}" if len(value) >= 12 else ("set" if value else None)
    else:
        out["value"] = value
    return out


# ---- is each group ready, and does it work -----------------------------------

def ai_provider() -> str:
    return settings.DEFAULT_AI_PROVIDER or "anthropic"


def ai_key() -> str:
    key = (settings.ANTHROPIC_API_KEY if ai_provider() == "anthropic" else settings.DEFAULT_AI_KEY) or ""
    key = key.strip()
    return key if len(key) > 20 and not key.endswith("...") else ""


def configured(group: str) -> bool:
    from app.services.mailer import email_configured

    return {
        "ai": lambda: bool(ai_key()),
        "embeddings": lambda: bool(settings.EMBEDDINGS_API_KEY),
        "google": lambda: bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "email": email_configured,
        "stripe": lambda: bool(settings.STRIPE_SECRET_KEY),
        "razorpay": lambda: bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET),
    }[group]()


async def _get(url: str, **kwargs) -> int:
    async with httpx.AsyncClient(timeout=20) as client:
        return (await client.get(url, **kwargs)).status_code


def _smtp_login() -> None:
    port = settings.SMTP_PORT
    server = smtplib.SMTP_SSL(settings.SMTP_HOST, port, timeout=15) if port == 465 else smtplib.SMTP(settings.SMTP_HOST, port, timeout=15)
    with server:
        if port != 465:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)


async def _try_ai() -> tuple[bool, str]:
    from app.core import providers
    from app.core.ai import FAST, AsyncAnthropic

    provider, ask = ai_provider(), [{"role": "user", "content": "Reply with the word OK."}]
    if provider == "anthropic":
        model = settings.DEFAULT_AI_MODEL or FAST
        await AsyncAnthropic(api_key=ai_key()).messages.create(model=model, max_tokens=5, messages=ask)
    else:
        model = providers.model_for(provider, "", "fast", settings.DEFAULT_AI_MODEL or None)
        if not model:
            return False, "Enter a model name for this provider"
        await providers.chat(provider, settings.DEFAULT_AI_BASE_URL or None, ai_key(), model, messages=ask, max_tokens=5, timeout=30)
    return True, f"{providers.PROVIDERS[provider]['name']} answered with the model {model}"


async def try_out(group: str) -> tuple[bool | None, str]:
    """Make one small real call with the group's settings. None means it cannot be checked from here."""
    from app.core import providers

    if group not in GROUPS:
        raise SettingError("There is no such group of settings")
    if not configured(group):
        return False, "Not set up yet"
    try:
        if group == "ai":
            return await _try_ai()
        if group == "embeddings":
            await providers.embed(settings.EMBEDDINGS_BASE_URL, settings.EMBEDDINGS_API_KEY, settings.EMBEDDINGS_MODEL, ["wiseflow"])
            return True, f"Answered with the model {settings.EMBEDDINGS_MODEL}"
        if group == "stripe":
            status = await _get("https://api.stripe.com/v1/balance", headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"})
            return (True, "Stripe accepted the key") if status == 200 else (False, f"Stripe did not accept the key (status {status})")
        if group == "razorpay":
            status = await _get("https://api.razorpay.com/v1/payments?count=1", auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            return (True, "Razorpay accepted the key") if status == 200 else (False, f"Razorpay did not accept the key (status {status})")
        if group == "email":
            await asyncio.to_thread(_smtp_login)
            return True, f"{settings.SMTP_HOST} accepted the sign-in. No email was sent."
        return None, "Google sign-in can only be checked by signing in with Google."
    except providers.ProviderError as e:
        return False, str(e)
    except smtplib.SMTPAuthenticationError:
        return False, "The mail server did not accept the user name and password"
    except (smtplib.SMTPException, OSError):
        return False, "The mail server could not be reached at that address and port"
    except httpx.HTTPError:
        return False, "The service could not be reached"
    except Exception as e:
        return False, _why(e)


def _why(error: Exception) -> str:
    """A sentence for a failed AI call, without anything from the request in it."""
    status = getattr(error, "status_code", None)
    text = str(error).lower()
    if status in (401, 403):
        return "The AI provider did not accept the key"
    if "credit" in text or "quota" in text or "billing" in text:
        return "The AI provider says the account is out of credit"
    if status == 404:
        return "The AI provider does not know that model"
    if status == 429:
        return "The AI provider says the key is sending too fast"
    return f"The call failed ({type(error).__name__})"


def key_problem(error: Exception) -> str | None:
    """The sentence above, but only when the failure means the key itself needs attention."""
    why = _why(error)
    return why if "did not accept" in why or "out of credit" in why or "out of quota" in str(error) else None


def _check_row(group: str, ok: bool | None, detail: str) -> tuple[str, str]:
    return f"check:{group}", encrypt(json.dumps({"ok": ok, "detail": detail[:300], "at": datetime.now(timezone.utc).isoformat()}))


async def remember_check(db, group: str, ok: bool | None, detail: str) -> None:
    key, value = _check_row(group, ok, detail)
    row = await db.get(PlatformSetting, key)
    if row:
        row.value_encrypted = value
    else:
        db.add(PlatformSetting(key=key, value_encrypted=value))
    await db.flush()


def note_failure(group: str, detail: str) -> None:
    """Called from a failed AI call, outside any request. Blocking; never raises."""
    from app.core.ai import _engine

    key, value = _check_row(group, False, detail)
    try:
        with _engine().begin() as db:
            table = PlatformSetting.__table__
            db.execute(table.delete().where(table.c.key == key))
            db.execute(table.insert().values(key=key, value_encrypted=value))
    except Exception as e:
        log.debug("A key problem was not recorded: %s", type(e).__name__)


async def overview(db) -> list[dict]:
    """Every group, its settings (secrets masked) and the result of its last test."""
    rows = (await db.execute(select(PlatformSetting).where(PlatformSetting.key.like("check:%")))).scalars().all()
    checks = {}
    for row in rows:
        try:
            checks[row.key[6:]] = json.loads(decrypt(row.value_encrypted) or "")
        except ValueError:
            pass
    return [{"id": group, "title": title, "about": about, "configured": configured(group),
             "fields": [_shown(key) for key, _, _ in fields], "last_check": checks.get(group)}
            for group, (title, about, fields) in GROUPS.items()]


# ---- the monthly allowance on the platform's AI key --------------------------

_spend: dict[str, tuple[float, float]] = {}   # organisation -> (when it was worked out, US dollars this month)


def month_spend(organization_id: str) -> float:
    """What the organisation's calls on the platform's key cost so far this month. Blocking; cached for a minute."""
    from sqlalchemy import func

    from app.core.ai import _engine, cost
    from app.models.integration import AiUsage

    cached = _spend.get(organization_id)
    if cached and time.monotonic() - cached[0] < 60:
        return cached[1]
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = 0.0
    try:
        with _engine().connect() as db:
            rows = db.execute(select(AiUsage.model, func.sum(AiUsage.input_tokens), func.sum(AiUsage.output_tokens))
                              .where(AiUsage.organization_id == organization_id, AiUsage.own_key.is_(False), AiUsage.created_at >= start)
                              .group_by(AiUsage.model)).all()
        # A model with no known price counts as nothing, so the allowance is a floor, not an exact bill.
        total = sum(cost(model, tokens_in or 0, tokens_out or 0) or 0 for model, tokens_in, tokens_out in rows)
    except Exception as e:
        log.debug("AI spend could not be worked out: %s", type(e).__name__)
    _spend[organization_id] = (time.monotonic(), total)
    return total
