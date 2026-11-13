"""documents for Wise to answer from

Revision ID: 015
Revises: 014
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wise_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_wise_documents_organization_id", "wise_documents", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_wise_documents_organization_id", table_name="wise_documents")
    op.drop_table("wise_documents")
