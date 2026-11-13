"""API keys, integrations and issues created from findings

Revision ID: 009
Revises: 008
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("secret_encrypted", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "kind", name="uq_integration_org_kind"),
    )
    op.create_index("ix_integrations_organization_id", "integrations", ["organization_id"])
    op.create_table(
        "tracker_issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("audit_id", sa.String(36), sa.ForeignKey("audit_jobs.id"), nullable=False),
        sa.Column("finding_ref", sa.String(64), nullable=False),
        sa.Column("issue_key", sa.String(64), nullable=False),
        sa.Column("issue_url", sa.String(1024), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("audit_id", "finding_ref", name="uq_tracker_issue_finding"),
    )
    op.create_index("ix_tracker_issues_audit_id", "tracker_issues", ["audit_id"])


def downgrade() -> None:
    for table, index in (("tracker_issues", "ix_tracker_issues_audit_id"), ("integrations", "ix_integrations_organization_id"), ("api_keys", "ix_api_keys_organization_id")):
        op.drop_index(index, table_name=table)
        op.drop_table(table)
