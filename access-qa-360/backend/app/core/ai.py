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


def record_usage(model: str, purpose: str, input_tokens: int, output_tokens: int, ok: bool, context: dict | None = None) -> None:
    """Write one row. Blocking; never raises."""
    context = context if context is not None else ai_context.get()
    try:
        with _engine().begin() as db:
            db.execute(
                text(
                    "INSERT INTO ai_usage (id, organization_id, audit_id, model, purpose, input_tokens, output_tokens, ok, created_at) "
                    "VALUES (:id, :org, :audit, :model, :purpose, :inp, :out, :ok, CURRENT_TIMESTAMP)"
                ),
                {"id": str(uuid.uuid4()), "org": context.get("organization_id"), "audit": context.get("audit_id"),
                 "model": str(model)[:64], "purpose": purpose[:64], "inp": int(input_tokens or 0), "out": int(output_tokens or 0), "ok": ok},
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


def ai_client(purpose: str) -> AsyncAnthropic:
    """
    An async client whose messages.create is counted under `purpose`.
    The organisation in `ai_context` may have chosen a quality level and supplied
    its own key; both are applied here, so no feature has to know about them.
    """
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    create = client.messages.create

    async def counted(*args, **kwargs):
        context = ai_context.get()
        if "model" in kwargs:
            kwargs["model"] = choose_model(kwargs["model"], context.get("quality"))
        model = kwargs.get("model", "unknown")
        call = AsyncAnthropic(api_key=context["api_key"]).messages.create if context.get("api_key") else create
        try:
            message = await call(*args, **kwargs)
        except Exception:
            await asyncio.to_thread(record_usage, model, purpose, 0, 0, False, context)
            raise
        await asyncio.to_thread(record_usage, model, purpose, *_tokens(message), True, context)
        return message

    client.messages.create = counted  # type: ignore[method-assign]
    return client


def sync_ai_client(purpose: str) -> Anthropic:
    """The same for code that runs outside the event loop (background workers)."""
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
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
            key = decrypt(org.ai_key_encrypted) if org.ai_key_encrypted else None
            if key:
                context["api_key"] = key
    return context
