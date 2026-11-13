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
    # Scans belong to the organisation, so every member can see them.
    organization_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=True, index=True)

    # Input params
    # "web" | "android" | "ios" | "code" (uploaded .zip) | "repo" (Git link) | "api" (uploaded OpenAPI file) | "chatbot".
    source_type: Mapped[str] = mapped_column(String(16), default="web", server_default="web", nullable=False)
    target_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    app_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mobile_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    apk_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Source code scans: the uploaded archive (deleted once scanned) or the repository link.
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    repo_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)      # branch to scan; the default branch when empty
    # Sign-in details for scanning behind a login. Encrypted, and wiped as soon as the scan ends.
    login_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Chatbot scans: how to send a message to the bot and where its reply is in the answer.
    chatbot_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # What started the scan when it was not a person: {"kind": "schedule", ...} or {"kind": "pull_request", ...}
    trigger: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # What the user asked for: any of "security", "manual", "playwright", "appium"
    outputs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    depth: Mapped[str] = mapped_column(String(16), default="standard", server_default="standard", nullable=False)
    # Set when the user confirms they may test this app; nothing runs before that.
    ownership_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    @property
    def label(self) -> str:
        repo = "/".join(self.repo_url.removesuffix(".git").split("/")[3:]) if self.repo_url else None
        return self.app_name or self.source_filename or repo or self.target_url or "Untitled app"

    @property
    def target_key(self) -> str:
        """Scans with the same key are scans of the same thing, so they can be compared."""
        if self.source_type == "web":
            return "web:" + (self.target_url or "").rstrip("/").lower()
        if self.source_type == "repo":
            return "repo:" + (self.repo_url or "").removesuffix(".git").lower()
        return f"{self.source_type}:{(self.app_name or self.source_filename or '').lower()}"

    @property
    def is_code(self) -> bool:
        return self.source_type in ("code", "repo")

    @property
    def has_mobile_input(self) -> bool:
        return bool(self.apk_path or self.ipa_path or self.mobile_url)

    @property
    def allowed_outputs(self) -> list[str]:
        if self.source_type in ("android", "ios"):
            return ["security", "manual", "appium"]
        if self.source_type in ("api", "chatbot"):
            return ["security", "manual"]
        if self.is_code:
            # Automation scripts need a running app to be written against, so they are not offered here.
            return ["security", "manual"]
        return ["security", "manual", "playwright"] + (["appium"] if self.has_mobile_input else [])

    @property
    def exports(self) -> list[str]:
        """Which downloads exist for this job right now."""
        import os

        t1, t2, t4 = self.tier1_result or {}, self.tier2_result or {}, self.tier4_result or {}
        found = []
        if self.report_pdf_path and os.path.exists(self.report_pdf_path):
            found.append("report")
        if t4.get("test_cases"):
            found.append("test-cases")
        if (t1.get("playwright_tests") or "").strip():
            found.append("playwright")
        if (t2.get("appium_tests") or "").strip():
            found.append("appium")
        if self.started_at:
            found.append("results")
        return found
