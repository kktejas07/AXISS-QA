"""audit jobs: source type, chosen outputs, depth, start and consent times

Revision ID: 005
Revises: 004
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_jobs", sa.Column("source_type", sa.String(16), nullable=False, server_default="web"))
    op.add_column("audit_jobs", sa.Column("source_filename", sa.String(255), nullable=True))
    op.add_column("audit_jobs", sa.Column("outputs", sa.JSON, nullable=True))
    op.add_column("audit_jobs", sa.Column("depth", sa.String(16), nullable=False, server_default="standard"))
    op.add_column("audit_jobs", sa.Column("ownership_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("audit_jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    # Audits created before this change started immediately.
    op.execute("UPDATE audit_jobs SET started_at = created_at")
    # Mobile-only jobs have no web address.
    op.alter_column("audit_jobs", "target_url", existing_type=sa.String(2048), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE audit_jobs SET target_url = '' WHERE target_url IS NULL")
    op.alter_column("audit_jobs", "target_url", existing_type=sa.String(2048), nullable=False)
    for col in ("started_at", "ownership_confirmed_at", "depth", "outputs", "source_filename", "source_type"):
        op.drop_column("audit_jobs", col)
