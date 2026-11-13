"""scheduled scans, and what started a scan

Revision ID: 013
Revises: 012
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_jobs", sa.Column("repo_ref", sa.String(255), nullable=True))
    op.add_column("audit_jobs", sa.Column("trigger", sa.JSON, nullable=True))
    op.create_table(
        "scan_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("target", sa.String(2048), nullable=False),
        sa.Column("outputs", sa.JSON, nullable=False),
        sa.Column("depth", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_audit_id", sa.String(36), nullable=True),
        sa.Column("last_note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scan_schedules_organization_id", "scan_schedules", ["organization_id"])
    op.create_index("ix_scan_schedules_next_run_at", "scan_schedules", ["next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_scan_schedules_next_run_at", table_name="scan_schedules")
    op.drop_index("ix_scan_schedules_organization_id", table_name="scan_schedules")
    op.drop_table("scan_schedules")
    op.drop_column("audit_jobs", "trigger")
    op.drop_column("audit_jobs", "repo_ref")
