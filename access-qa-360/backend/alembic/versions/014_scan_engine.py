"""sign-in details for scans, two-step sign-in, required Google sign-in

Revision ID: 014
Revises: 013
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_jobs", sa.Column("login_encrypted", sa.Text, nullable=True))
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.Text, nullable=True))
    op.add_column("users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("totp_last_counter", sa.BigInteger, nullable=True))
    op.add_column("organizations", sa.Column("require_sso", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("organizations", "require_sso")
    op.drop_column("users", "totp_last_counter")
    op.drop_column("users", "totp_enabled_at")
    op.drop_column("users", "totp_secret_encrypted")
    op.drop_column("audit_jobs", "login_encrypted")
