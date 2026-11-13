"""organisations, invites, admin audit log; users and scans belong to an organisation

Revision ID: 006
Revises: 005
Create Date: 2026-11-13
"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(16), nullable=False, server_default="individual"),
        sa.Column("seat_limit", sa.Integer, nullable=True),
        sa.Column("scan_limit", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "invites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.add_column("users", sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True))
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.add_column("users", sa.Column("org_role", sa.String(16), nullable=False, server_default="owner"))
    op.add_column("audit_jobs", sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True))
    op.create_index("ix_audit_jobs_organization_id", "audit_jobs", ["organization_id"])

    # Every existing user becomes the owner of their own individual organisation,
    # and their scans move into it.
    conn = op.get_bind()
    for user_id, full_name in conn.execute(sa.text("SELECT id, full_name FROM users")).fetchall():
        org_id = str(uuid.uuid4())
        conn.execute(
            sa.text("INSERT INTO organizations (id, name, account_type, seat_limit, status) VALUES (:id, :name, 'individual', 1, 'active')"),
            {"id": org_id, "name": f"{full_name}'s workspace"},
        )
        conn.execute(sa.text("UPDATE users SET organization_id = :org, org_role = 'owner' WHERE id = :uid"), {"org": org_id, "uid": user_id})
        conn.execute(sa.text("UPDATE audit_jobs SET organization_id = :org WHERE created_by = :uid"), {"org": org_id, "uid": user_id})


def downgrade() -> None:
    op.drop_index("ix_audit_jobs_organization_id", table_name="audit_jobs")
    op.drop_column("audit_jobs", "organization_id")
    op.drop_column("users", "org_role")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "organization_id")
    op.drop_table("admin_audit_log")
    op.drop_table("invites")
    op.drop_table("organizations")
