"""API keys for pipelines, and the organisation's link to its issue tracker."""
from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


def _id() -> str:
    return str(uuid.uuid4())


class ApiKey(Base):
    """Lets a build pipeline start scans for an organisation. Only a hash of the key is stored."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    # Scans started with the key are recorded as started by this person.
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)        # shown in lists so a key can be recognised
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Integration(Base):
    """One connection per kind per organisation, e.g. kind "jira". The secret is stored encrypted."""

    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("organization_id", "kind", name="uq_integration_org_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrackerIssue(Base):
    """An issue created in the tracker from one finding of a scan."""

    __tablename__ = "tracker_issues"
    __table_args__ = (UniqueConstraint("audit_id", "finding_ref", name="uq_tracker_issue_finding"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    audit_id: Mapped[str] = mapped_column(String(36), ForeignKey("audit_jobs.id"), nullable=False, index=True)
    # Which finding: "security:3" or "mobile:0" (the list it is in and its position there).
    finding_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    issue_key: Mapped[str] = mapped_column(String(64), nullable=False)
    issue_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiUsage(Base):
    """One AI call: which model, how many tokens, and which organisation's scan it was for."""

    __tablename__ = "ai_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    audit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # True when the organisation's own key paid for the call, so it does not count towards its allowance.
    own_key: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
