"""platform settings, AI spending cap and whose key paid for a call

Revision ID: 019
Revises: 018
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("organizations", sa.Column("ai_monthly_cap_usd", sa.Integer(), nullable=True))
    op.add_column("ai_usage", sa.Column("own_key", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("ai_usage", "own_key")
    op.drop_column("organizations", "ai_monthly_cap_usd")
    op.drop_table("platform_settings")
