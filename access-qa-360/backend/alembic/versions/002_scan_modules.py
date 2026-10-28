"""scan, vulnerability, qa_gap, test_case, report tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-15
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("scan_type", sa.Enum("passive", "active", "hybrid", name="scantype"), default="passive"),
        sa.Column("status", sa.Enum("queued", "crawling", "scanning", "analyzing", "completed", "failed", name="scanstatus"), default="queued"),
        sa.Column("auth_config", sa.JSON, nullable=True),
        sa.Column("scope_include", sa.Text, nullable=True),
        sa.Column("scope_exclude", sa.Text, nullable=True),
        sa.Column("crawl_depth", sa.Integer, default=3),
        sa.Column("rate_limit", sa.Integer, default=10),
        sa.Column("scan_profile", sa.Enum("owasp_top10", "pci_dss", "hipaa", "custom", name="scanprofile"), default="owasp_top10"),
        sa.Column("progress", sa.Integer, default=0),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table("vulnerabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("severity", sa.Enum("critical", "high", "medium", "low", "informational", name="severity"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("cvss_score", sa.Float, nullable=True),
        sa.Column("cwe_id", sa.String(20), nullable=True),
        sa.Column("cve_id", sa.String(20), nullable=True),
        sa.Column("affected_url", sa.String(2048), nullable=False),
        sa.Column("affected_parameter", sa.String(255), nullable=True),
        sa.Column("proof_request", sa.Text, nullable=True),
        sa.Column("proof_response", sa.Text, nullable=True),
        sa.Column("remediation", sa.Text, nullable=True),
        sa.Column("fix_effort", sa.Enum("low", "medium", "high", name="fixeffort"), nullable=True),
        sa.Column("owasp_category", sa.String(100), nullable=True),
        sa.Column("status", sa.Enum("open", "confirmed", "fixed", "false_positive", name="vulnstatus"), default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("qa_gaps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("route_path", sa.String(2048), nullable=False),
        sa.Column("gap_type", sa.Enum("uncovered", "partially_covered", "missing_edge_case", "accessibility", "business_logic", "orphaned_test", name="gaptype"), nullable=False),
        sa.Column("risk_level", sa.Enum("critical", "high", "medium", "low", name="risklevel"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("test_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("test_type", sa.Enum("manual", "unit", "smoke", "regression", "integration", "performance", "accessibility", "security_regression", name="testtype"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("preconditions", sa.Text, nullable=True),
        sa.Column("steps", sa.JSON, nullable=True),
        sa.Column("expected_result", sa.Text, nullable=True),
        sa.Column("code_content", sa.Text, nullable=True),
        sa.Column("language", sa.Enum("python", "typescript", "javascript", "gherkin", "k6", name="testlanguage"), nullable=True),
        sa.Column("status", sa.Enum("generated", "approved", "exported", name="testcasestatus"), default="generated"),
        sa.Column("priority", sa.Enum("critical", "high", "medium", "low", name="priority"), default="medium"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("report_type", sa.Enum("executive_summary", "vulnerability", "qa_gap", "test_bundle", "compliance", "diff", name="reporttype"), nullable=False),
        sa.Column("format", sa.Enum("pdf", "json", "docx", "csv", name="reportformat"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("reports")
    op.drop_table("test_cases")
    op.drop_table("qa_gaps")
    op.drop_table("vulnerabilities")
    op.drop_table("scans")
