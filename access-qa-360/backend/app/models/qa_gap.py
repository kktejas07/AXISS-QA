from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


class GapType(str, enum.Enum):
    uncovered = "uncovered"
    partially_covered = "partially_covered"
    missing_edge_case = "missing_edge_case"
    accessibility = "accessibility"
    business_logic = "business_logic"
    orphaned_test = "orphaned_test"


class RiskLevel(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class QAGap(Base):
    __tablename__ = "qa_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False)
    route_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    gap_type: Mapped[GapType] = mapped_column(Enum(GapType), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan: Mapped["Scan"] = relationship("Scan", back_populates="qa_gaps")
