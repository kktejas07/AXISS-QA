from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    suite_id: Mapped[str] = mapped_column(String(36), ForeignKey("suites.id"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.queued)
    triggered_by: Mapped[str] = mapped_column(String(50), default="manual")
    branch: Mapped[str | None] = mapped_column(String(255))
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    tests_total: Mapped[int | None] = mapped_column(Integer)
    tests_passed: Mapped[int | None] = mapped_column(Integer)
    tests_failed: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    stdout_log: Mapped[str | None] = mapped_column(Text)
    triage_summary: Mapped[str | None] = mapped_column(Text)
    screenshot_urls: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    suite: Mapped["Suite"] = relationship("Suite", back_populates="runs")
