"""other AI providers, and stored embeddings for Wise

Revision ID: 017
Revises: 016
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("ai_provider", sa.String(24), nullable=False, server_default="anthropic"))
    op.add_column("organizations", sa.Column("ai_model", sa.String(120), nullable=True))
    op.add_column("organizations", sa.Column("ai_base_url", sa.String(500), nullable=True))
    op.create_table(
        "wise_embeddings",
        sa.Column("hash", sa.String(40), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("vector", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_wise_embeddings_organization_id", "wise_embeddings", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_wise_embeddings_organization_id", table_name="wise_embeddings")
    op.drop_table("wise_embeddings")
    op.drop_column("organizations", "ai_base_url")
    op.drop_column("organizations", "ai_model")
    op.drop_column("organizations", "ai_provider")
