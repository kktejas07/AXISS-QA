"""initial schema

Revision ID: 001
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("suites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("feature_description", sa.Text, nullable=False),
        sa.Column("generated_code", sa.Text),
        sa.Column("status", sa.Enum("draft", "active", "archived", name="suitestatus"), default="draft"),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("suite_id", sa.String(36), sa.ForeignKey("suites.id"), nullable=False),
        sa.Column("status", sa.Enum("queued", "running", "passed", "failed", "error", name="runstatus"), default="queued"),
        sa.Column("triggered_by", sa.String(50), default="manual"),
        sa.Column("branch", sa.String(255)),
        sa.Column("commit_sha", sa.String(40)),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("tests_total", sa.Integer),
        sa.Column("tests_passed", sa.Integer),
        sa.Column("tests_failed", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("stdout_log", sa.Text),
        sa.Column("triage_summary", sa.Text),
        sa.Column("screenshot_urls", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("runs")
    op.drop_table("suites")
    op.drop_table("projects")
    op.drop_table("users")
