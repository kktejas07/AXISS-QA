"""Scans that run by themselves: on a timetable."""
from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

FREQUENCIES = ("daily", "weekly", "monthly")


class ScanSchedule(Base):
    """Re-scan one website or repository every day, week or month."""

    __tablename__ = "scan_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    # Scans it starts are recorded as started by this person, who confirmed they may test the target.
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)          # "web" | "repo"
    target: Mapped[str] = mapped_column(String(2048), nullable=False)             # web address or repository link
    outputs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    depth: Mapped[str] = mapped_column(String(16), default="standard", nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_audit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_note: Mapped[str | None] = mapped_column(String(255), nullable=True)     # why the last run was skipped, if it was
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
