"""organisations: subscription details

Revision ID: 011
Revises: 010
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

COLUMNS = [
    sa.Column("billing_provider", sa.String(16), nullable=True),
    sa.Column("billing_customer_id", sa.String(64), nullable=True),
    sa.Column("billing_subscription_id", sa.String(64), nullable=True),
    sa.Column("billing_status", sa.String(16), nullable=True),
    sa.Column("billing_seats", sa.Integer, nullable=True),
    sa.Column("billing_period_end", sa.DateTime(timezone=True), nullable=True),
    sa.Column("billing_cancel_at_period_end", sa.Boolean, nullable=False, server_default=sa.false()),
]


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("organizations", column.copy())
    op.create_index("ix_organizations_billing_subscription_id", "organizations", ["billing_subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_organizations_billing_subscription_id", table_name="organizations")
    for column in reversed(COLUMNS):
        op.drop_column("organizations", column.name)
