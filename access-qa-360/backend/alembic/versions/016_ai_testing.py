"""chatbot scans and per-organisation AI settings

Revision ID: 016
Revises: 015
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_jobs", sa.Column("chatbot_config", sa.JSON, nullable=True))
    op.add_column("organizations", sa.Column("ai_quality", sa.String(16), nullable=False, server_default="balanced"))
    op.add_column("organizations", sa.Column("ai_key_encrypted", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "ai_key_encrypted")
    op.drop_column("organizations", "ai_quality")
    op.drop_column("audit_jobs", "chatbot_config")
