"""What the public site needs from the server: the contact form and a status check. Plus the admin's view of contact requests."""
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.platform import ContactRequest
from app.models.user import User
from app.services.mailer import send_email
from app.services.orgs import log_admin_action

router = APIRouter(tags=["public"])
admin = APIRouter(prefix="/admin/contacts", tags=["admin"], dependencies=[Depends(require_super_admin)])

KINDS = {"demo": "A demo", "pricing": "A price for my team", "enterprise": "Enterprise terms", "other": "Something else"}
# At most this many messages from one address in an hour. Kept in memory: good enough to stop a script filling the table.
PER_HOUR = 5
_recent: dict[str, deque] = defaultdict(deque)


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str | None = Field(default=None, max_length=160)
    kind: Literal["demo", "pricing", "enterprise", "other"] = "demo"
    message: str = Field(min_length=10, max_length=4000)
    # A field people never see. Only a script fills it in.
    website: str | None = Field(default=None, max_length=200)


def _one_line(value: str) -> str:
    return " ".join(value.split())


@router.post("/public/contact", status_code=201)
async def contact(body: ContactIn, request: Request, db: AsyncSession = Depends(get_db)):
    """A message from the contact form. Stored for the admin console, and emailed to sales when email is set up."""
    if body.website:
        return {"received": True}          # a script: say thanks, keep nothing
    sender = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown"))
    now, seen = time.monotonic(), _recent[sender]
    while seen and now - seen[0] > 3600:
        seen.popleft()
    if len(seen) >= PER_HOUR:
        raise HTTPException(429, "That is a lot of messages in an hour. Try again later.")
    seen.append(now)

    row = ContactRequest(id=str(uuid.uuid4()), name=_one_line(body.name), email=str(body.email).lower(), company=_one_line(body.company) if body.company else None,
                         kind=body.kind, message=body.message.strip())
    db.add(row)
    await db.flush()
    if settings.SALES_EMAIL:
        await send_email(settings.SALES_EMAIL, f"Wiseflow contact: {KINDS[row.kind]} ({row.name})",
                         f"From: {row.name} <{row.email}>\nCompany: {row.company or 'not given'}\nAbout: {KINDS[row.kind]}\n\n{row.message}\n\nReply to them directly. This is also in the admin console under Contact requests.")
    return {"received": True}


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    """Is the service up? Public, so it says only yes or no for each part and nothing about how it is built."""
    try:
        await db.execute(text("SELECT 1"))
        database = True
    except Exception:
        database = False
    return {"ok": database, "checked_at": datetime.now(timezone.utc), "parts": [{"name": "Website and API", "ok": True}, {"name": "Database", "ok": database}]}


def _out(row: ContactRequest) -> dict:
    return {"id": row.id, "name": row.name, "email": row.email, "company": row.company, "kind": row.kind, "about": KINDS.get(row.kind, row.kind),
            "message": row.message, "created_at": row.created_at, "handled_at": row.handled_at}


@admin.get("")
async def contacts(db: AsyncSession = Depends(get_db)):
    """Contact requests, the ones still waiting first, then newest first."""
    rows = (await db.execute(select(ContactRequest).order_by(ContactRequest.handled_at.is_not(None), ContactRequest.created_at.desc()).limit(300))).scalars().all()
    return [_out(r) for r in rows]


class Handled(BaseModel):
    handled: bool


@admin.put("/{contact_id}")
async def mark(contact_id: str, body: Handled, db: AsyncSession = Depends(get_db), me: User = Depends(require_super_admin)):
    row = await db.get(ContactRequest, contact_id)
    if not row:
        raise HTTPException(404, "That request was not found")
    row.handled_at, row.handled_by = (datetime.now(timezone.utc), me.id) if body.handled else (None, None)
    await log_admin_action(db, me, "contact.handled" if body.handled else "contact.reopened", row.email)
    await db.flush()
    return _out(row)
