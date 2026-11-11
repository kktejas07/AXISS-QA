"""
AuditJob — umbrella record tying all 5 audit tiers together.

One AuditJob per audit request (URL / app-name input).
Stores per-tier JSON blobs so the frontend can display each tier's results
independently while also accessing the unified report.
"""
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, Enum, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


class AuditStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    partial = "partial"       # Some tiers failed but results available


class AuditJob(Base):
    __tablename__ = "audit_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # Input params
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    app_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mobile_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    apk_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Overall status
    status: Mapped[AuditStatus] = mapped_column(Enum(AuditStatus), default=AuditStatus.queued)
    progress: Mapped[int] = mapped_column(Integer, default=0)      # 0-100

    # Per-tier status
    tier1_status: Mapped[str] = mapped_column(String(32), default="pending")
    tier2_status: Mapped[str] = mapped_column(String(32), default="pending")
    tier3_status: Mapped[str] = mapped_column(String(32), default="pending")
    tier4_status: Mapped[str] = mapped_column(String(32), default="pending")
    tier5_status: Mapped[str] = mapped_column(String(32), default="pending")

    # Per-tier JSON results
    tier1_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # web audit
    tier2_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # mobile audit
    tier3_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # api/cyber
    tier4_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # manual QA checklists
    tier5_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # unified report

    # Computed scores
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 0-100
    coverage_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    high_count: Mapped[int] = mapped_column(Integer, default=0)
    total_test_cases: Mapped[int] = mapped_column(Integer, default=0)
    total_pages_audited: Mapped[int] = mapped_column(Integer, default=0)

    # Executive summary (Claude-generated, stored separately for quick display)
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped["User"] = relationship("User", lazy="select")
