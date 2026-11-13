"""Organisations, invitations to join them, and the super admin audit log.

Every user belongs to exactly one organisation. Someone who signs up on their
own gets an "individual" organisation of one; a "team" or "enterprise"
organisation has several members, each with one of four roles.
"""
from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

ACCOUNT_TYPES = ("individual", "team", "enterprise")
ORG_ROLES = ("owner", "admin", "member", "viewer")


def _id() -> str:
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), default="individual", server_default="individual", nullable=False)
    # None means no limit.
    seat_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    scan_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # scans started per calendar month
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)  # active | suspended
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Paid subscription, when the organisation pays by card. Organisations a super admin
    # set up by hand have no provider and are not affected by any of this.
    billing_provider: Mapped[str | None] = mapped_column(String(16), nullable=True)          # "stripe" | "razorpay"
    billing_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    billing_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    billing_status: Mapped[str | None] = mapped_column(String(16), nullable=True)            # active | past_due | cancelled
    billing_seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billing_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # Members must sign in with Google; passwords are refused. The owner is exempt, so nobody can be locked out.
    require_sso: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # AI settings: "fast", "balanced" or "best", and optionally the organisation's own Anthropic key (encrypted).
    ai_quality: Mapped[str] = mapped_column(String(16), default="balanced", server_default="balanced", nullable=False)
    ai_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which provider that key is for ("anthropic", "openai", "gemini", ...), an exact model name if the
    # organisation wants one, and the address for a "custom" OpenAI-compatible provider.
    ai_provider: Mapped[str] = mapped_column(String(24), default="anthropic", server_default="anthropic", nullable=False)
    ai_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Most this organisation may spend on the platform's AI key in a month, in whole US dollars.
    # None means the platform-wide figure applies.
    ai_monthly_cap_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminAuditLog(Base):
    """What a super admin changed, and when. Written by the admin routes; never edited."""

    __tablename__ = "admin_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    actor_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PasswordReset(Base):
    """A single-use link for choosing a new password. Only a hash of the token is stored."""

    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
