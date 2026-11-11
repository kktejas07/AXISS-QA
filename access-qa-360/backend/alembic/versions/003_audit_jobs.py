"""add audit_jobs table

Revision ID: 003
Revises: 002
Create Date: 2025-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        # inputs
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("app_name", sa.String(256), nullable=True),
        sa.Column("mobile_url", sa.String(2048), nullable=True),
        sa.Column("apk_path", sa.Text, nullable=True),
        sa.Column("ipa_path", sa.Text, nullable=True),
        # status
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tier1_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("tier2_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("tier3_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("tier4_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("tier5_status", sa.String(32), nullable=False, server_default="pending"),
        # tier results (JSON)
        sa.Column("tier1_result", sa.JSON, nullable=True),
        sa.Column("tier2_result", sa.JSON, nullable=True),
        sa.Column("tier3_result", sa.JSON, nullable=True),
        sa.Column("tier4_result", sa.JSON, nullable=True),
        sa.Column("tier5_result", sa.JSON, nullable=True),
        # scores
        sa.Column("risk_score", sa.Integer, nullable=True),
        sa.Column("coverage_pct", sa.Integer, nullable=True),
        sa.Column("critical_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("high_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_test_cases", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_pages_audited", sa.Integer, nullable=False, server_default="0"),
        # output
        sa.Column("executive_summary", sa.Text, nullable=True),
        sa.Column("report_pdf_path", sa.Text, nullable=True),
        # timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_audit_jobs_created_by", "audit_jobs", ["created_by"])
    op.create_index("ix_audit_jobs_status", "audit_jobs", ["status"])
    op.create_index("ix_audit_jobs_created_at", "audit_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_jobs_created_at", "audit_jobs")
    op.drop_index("ix_audit_jobs_status", "audit_jobs")
    op.drop_index("ix_audit_jobs_created_by", "audit_jobs")
    op.drop_table("audit_jobs")
