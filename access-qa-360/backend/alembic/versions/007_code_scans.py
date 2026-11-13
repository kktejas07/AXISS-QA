"""audit jobs: uploaded source archive and repository link

Revision ID: 007
Revises: 006
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_jobs", sa.Column("source_path", sa.Text, nullable=True))
    op.add_column("audit_jobs", sa.Column("repo_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_jobs", "repo_url")
    op.drop_column("audit_jobs", "source_path")
