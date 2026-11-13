"""What a team has decided about a finding: its status, who owns it, and why."""
from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

STATUSES = ("open", "fixed", "accepted", "false_positive")


class FindingState(Base):
    """
    Kept per target and per finding fingerprint, not per scan, so a decision made
    once ("this is a false positive") still stands on the next scan of the same thing.
    """

    __tablename__ = "finding_states"
    __table_args__ = (UniqueConstraint("organization_id", "target_key", "fingerprint", name="uq_finding_state"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(600), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
