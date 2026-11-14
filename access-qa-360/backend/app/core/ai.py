"""
The one place the app creates its AI clients, so every call is counted.

Each call's model and token counts are written to ai_usage (best effort: a
failure to record never affects the call). The organisation and scan come from
`ai_context`, which the scan runner sets for the duration of a scan.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import uuid
from functools import lru_cache

from anthropic import Anthropic, AsyncAnthropic
from sqlalchemy import create_engine, text

from app.core.config import settings

log = logging.getLogger(__name__)

# {"organization_id": ..., "audit_id": ...} while a scan runs; empty otherwise.
ai_context: contextvars.ContextVar[dict] = contextvars.ContextVar("ai_context", default={})


@lru_cache
def _engine():
    return create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=2)


class AiAllowanceUsed(Exception):
    """The organisation has used this month's allowance on the platform's AI key."""


# US dollars per million tokens (input, output). Models that are not listed are counted but not costed.
PRICES = {"claude-sonnet-4-5": (3.0, 15.0), "claude-haiku-4-5": (1.0, 5.0)}


def cost(model: str, tokens_in: int, tokens_out: int) -> float | None:
    for name, (price_in, price_out) in PRICES.items():
        if model.startswith(name):
            return round(tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out, 4)
    return None


def record_usage(model: str, purpose: str, input_tokens: int, output_tokens: int, ok: bool, context: dict | None = None) -> None:
    """Write one row. Blocking; never raises."""
    context = context if context is not None else ai_context.get()
    try:
        with _engine().begin() as db:
            db.execute(
                text(
                    "INSERT INTO ai_usage (id, organization_id, audit_id, model, purpose, input_tokens, output_tokens, ok, own_key, created_at) "
                    "VALUES (:id, :org, :audit, :model, :purpose, :inp, :out, :ok, :own, CURRENT_TIMESTAMP)"
                ),
                {"id": str(uuid.uuid4()), "org": context.get("organization_id"), "audit": context.get("audit_id"),
                 "model": str(model)[:64], "purpose": purpose[:64], "inp": int(input_tokens or 0), "out": int(output_tokens or 0), "ok": ok,
                 "own": bool(context.get("own_key"))},
            )
    except Exception as e:  # usage tracking must never break a scan
        log.debug("AI usage was not recorded: %s", type(e).__name__)


def _tokens(message) -> tuple[int, int]:
    usage = getattr(message, "usage", None)
    return getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0


# An organisation's choice of speed against quality. "balanced" keeps the model each feature was built with.
FAST, BEST = "claude-haiku-4-5", "claude-sonnet-4-5"
QUALITIES = {"fast": FAST, "balanced": None, "best": BEST}


def choose_model(asked: str, quality: str | None) -> str:
    return QUALITIES.get(quality or "balanced") or asked


def _claude(key: str, own: bool = False) -> AsyncAnthropic:
    """A Claude client. The platform's key may be for a Claude-compatible service at another address; an organisation's own key is always for Anthropic."""
    return AsyncAnthropic(api_key=key, base_url=None if own else (settings.ANTHROPIC_BASE_URL or None))


def ai_client(purpose: str) -> AsyncAnthropic:
    """
    An async client whose messages.create is counted under `purpose`.
    The organisation in `ai_context` may have chosen a quality level and supplied
    its own key; both are applied here, so no feature has to know about them.
    """
    client = _claude(settings.ANTHROPIC_API_KEY)
    made_with = (settings.ANTHROPIC_API_KEY, settings.ANTHROPIC_BASE_URL)
    create = client.messages.create

    async def counted(*args, **kwargs):
        from app.core import platform

        context = ai_context.get()
        own = bool(context.get("api_key"))
        context = {**context, "own_key": own}
        if not own:
            # The platform's key pays, so the organisation's monthly allowance applies.
            org, cap = context.get("organization_id"), context.get("cap") if context.get("cap") is not None else settings.AI_MONTHLY_CAP_USD
            if org and cap and await asyncio.to_thread(platform.month_spend, org) >= cap:
                raise AiAllowanceUsed("This organisation has used its AI allowance for the month")
            # And the platform's choice of provider and model.
            if platform.ai_provider() != "anthropic" and platform.ai_key():
                context.update(provider=platform.ai_provider(), api_key=platform.ai_key(), base_url=settings.DEFAULT_AI_BASE_URL or None)
            if settings.DEFAULT_AI_MODEL:
                context["model"] = settings.DEFAULT_AI_MODEL
            # Made here, not above, so a key replaced from the console is used at once.
            create_now = _claude(settings.ANTHROPIC_API_KEY).messages.create if (settings.ANTHROPIC_API_KEY, settings.ANTHROPIC_BASE_URL) != made_with else create
        else:
            create_now = create
        provider = context.get("provider") or "anthropic"
        if provider != "anthropic" and context.get("api_key"):
            # The organisation's own key with another provider: the same request, translated.
            from app.core import providers

            kwargs["model"] = providers.model_for(provider, kwargs.get("model", ""), context.get("quality"), context.get("model"))

            async def call(*_args, **kw):
                name = kw.pop("model")
                return await providers.chat(provider, context.get("base_url"), context["api_key"], name, **kw)
        else:
            if "model" in kwargs:
                kwargs["model"] = context.get("model") or choose_model(kwargs["model"], context.get("quality"))
            call = _claude(context["api_key"], own=True).messages.create if context.get("api_key") else create_now
        model = kwargs.get("model", "unknown")
        try:
            message = await call(*args, **kwargs)
        except Exception as e:
            await asyncio.to_thread(record_usage, model, purpose, 0, 0, False, context)
            if not own and platform.key_problem(e):
                await asyncio.to_thread(platform.note_failure, "ai", platform.key_problem(e))
            raise
        await asyncio.to_thread(record_usage, model, purpose, *_tokens(message), True, context)
        return message

    client.messages.create = counted  # type: ignore[method-assign]
    return client


def sync_ai_client(purpose: str) -> Anthropic:
    """The same for code that runs outside the event loop (background workers)."""
    if settings.ENVIRONMENT != "test":
        from app.core import platform

        platform.refresh_sync()
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, base_url=settings.ANTHROPIC_BASE_URL or None)
    create = client.messages.create

    def counted(*args, **kwargs):
        model = kwargs.get("model", "unknown")
        try:
            message = create(*args, **kwargs)
        except Exception:
            record_usage(model, purpose, 0, 0, False)
            raise
        record_usage(model, purpose, *_tokens(message), True)
        return message

    client.messages.create = counted  # type: ignore[method-assign]
    return client


async def org_context(db, organization_id: str | None, audit_id: str | None = None) -> dict:
    """What `ai_context` should hold for work done for this organisation: who it is for, and its AI settings."""
    context: dict = {"organization_id": organization_id, "audit_id": audit_id}
    if organization_id:
        from app.core.secrets import decrypt
        from app.models.organization import Organization

        org = await db.get(Organization, organization_id)
        if org:
            context["quality"] = org.ai_quality or "balanced"
            context["cap"] = org.ai_monthly_cap_usd
            key = decrypt(org.ai_key_encrypted) if org.ai_key_encrypted else None
            if key:
                # The provider, model and address only apply together with the organisation's own key.
                context.update(api_key=key, provider=org.ai_provider or "anthropic")
                if org.ai_model:
                    context["model"] = org.ai_model
                if org.ai_base_url:
                    context["base_url"] = org.ai_base_url
    return context
