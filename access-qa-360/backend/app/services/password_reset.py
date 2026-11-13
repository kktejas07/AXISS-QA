"""Single-use password reset links."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.organization import PasswordReset
from app.models.user import User

MAX_LINKS_PER_HOUR = 3


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def reset_url(token: str) -> str:
    return f"{settings.APP_URL.rstrip('/')}/reset-password?token={token}"


async def recent_link_count(db: AsyncSession, user_id: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    return (
        await db.execute(select(func.count()).select_from(PasswordReset).where(PasswordReset.user_id == user_id, PasswordReset.created_at >= since))
    ).scalar() or 0


async def create_reset(db: AsyncSession, user: User) -> tuple[str, datetime]:
    """Make a link for this user. Returns (token, expiry); the token itself is never stored."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_MINUTES)
    db.add(PasswordReset(user_id=user.id, token_hash=_hash(token), expires_at=expires))
    await db.flush()
    return token, expires


async def find_reset(db: AsyncSession, token: str) -> tuple[PasswordReset, User] | None:
    """The unused, unexpired link for this token and its active user, or None."""
    row = (await db.execute(select(PasswordReset).where(PasswordReset.token_hash == _hash(token or "")))).scalar_one_or_none()
    if not row or row.used_at is not None:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    user = await db.get(User, row.user_id)
    if not user or not user.is_active:
        return None
    return row, user


async def set_password(db: AsyncSession, user: User, password: str) -> None:
    """Change the password, sign out every existing session and cancel any outstanding reset links."""
    now = datetime.now(timezone.utc)
    user.hashed_password = get_password_hash(password)
    user.password_changed_at = now
    await db.execute(
        update(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)).values(used_at=now)
    )
    await db.flush()
