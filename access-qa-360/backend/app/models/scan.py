from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, Enum, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


class ScanType(str, enum.Enum):
    passive = "passive"
    active = "active"
    hybrid = "hybrid"


class ScanStatus(str, enum.Enum):
    queued = "queued"
    crawling = "crawling"
    scanning = "scanning"
    analyzing = "analyzing"
    completed = "completed"
    failed = "failed"


class ScanProfile(str, enum.Enum):
    owasp_top10 = "owasp_top10"
    pci_dss = "pci_dss"
    hipaa = "hipaa"
    custom = "custom"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    scan_type: Mapped[ScanType] = mapped_column(Enum(ScanType), default=ScanType.passive)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.queued)
    auth_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scope_include: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_exclude: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawl_depth: Mapped[int] = mapped_column(Integer, default=3)
    rate_limit: Mapped[int] = mapped_column(Integer, default=10)
    scan_profile: Mapped[ScanProfile] = mapped_column(Enum(ScanProfile), default=ScanProfile.owasp_top10)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="select")
    creator: Mapped["User"] = relationship("User", lazy="select")
    vulnerabilities: Mapped[list["Vulnerability"]] = relationship("Vulnerability", back_populates="scan", lazy="select")
    qa_gaps: Mapped[list["QAGap"]] = relationship("QAGap", back_populates="scan", lazy="select")
    test_cases: Mapped[list["TestCase"]] = relationship("TestCase", back_populates="scan", lazy="select")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="scan", lazy="select")
