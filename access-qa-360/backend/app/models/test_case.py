from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


class TestType(str, enum.Enum):
    manual = "manual"
    unit = "unit"
    smoke = "smoke"
    regression = "regression"
    integration = "integration"
    performance = "performance"
    accessibility = "accessibility"
    security_regression = "security_regression"


class TestLanguage(str, enum.Enum):
    python = "python"
    typescript = "typescript"
    javascript = "javascript"
    gherkin = "gherkin"
    k6 = "k6"


class TestCaseStatus(str, enum.Enum):
    generated = "generated"
    approved = "approved"
    exported = "exported"


class Priority(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False)
    test_type: Mapped[TestType] = mapped_column(Enum(TestType), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    preconditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[TestLanguage | None] = mapped_column(Enum(TestLanguage), nullable=True)
    status: Mapped[TestCaseStatus] = mapped_column(Enum(TestCaseStatus), default=TestCaseStatus.generated)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.medium)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan: Mapped["Scan"] = relationship("Scan", back_populates="test_cases")
