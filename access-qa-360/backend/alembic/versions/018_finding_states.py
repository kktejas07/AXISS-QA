"""status and owner for findings

Revision ID: 018
Revises: 017
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finding_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("target_key", sa.String(600), nullable=False),
        sa.Column("fingerprint", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("assignee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "target_key", "fingerprint", name="uq_finding_state"),
    )
    op.create_index("ix_finding_states_organization_id", "finding_states", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_finding_states_organization_id", table_name="finding_states")
    op.drop_table("finding_states")
