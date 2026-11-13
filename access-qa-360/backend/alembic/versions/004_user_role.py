"""add role to users

Revision ID: 004
Revises: 003
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing accounts become ordinary users; list emails in SUPER_ADMIN_EMAILS to promote them.
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="user"))


def downgrade() -> None:
    op.drop_column("users", "role")
