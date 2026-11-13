"""free accounts: 2 scans a month

Accounts created while the free allowance was 10 move to the new allowance of 2.
Paid accounts and limits an administrator set to another number are left alone.

Revision ID: 012
Revises: 011
Create Date: 2026-11-14
"""
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

FREE = "account_type = 'individual' AND billing_status IS NULL"


def upgrade() -> None:
    op.execute(f"UPDATE organizations SET scan_limit = 2 WHERE scan_limit = 10 AND {FREE}")


def downgrade() -> None:
    op.execute(f"UPDATE organizations SET scan_limit = 10 WHERE scan_limit = 2 AND {FREE}")
