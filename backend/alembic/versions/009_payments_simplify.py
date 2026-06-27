"""Checklist: simplify payments — all confirmed, no approval workflow

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-27

"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE payments
            SET status = 'confirmed',
                confirmed_at = COALESCE(confirmed_at, created_at),
                confirmed_by = COALESCE(confirmed_by, created_by),
                rejection_reason = NULL
            WHERE status IN ('pending', 'rejected')
            """
        )
    )
    op.alter_column(
        "payments",
        "status",
        existing_type=sa.String(length=10),
        server_default="confirmed",
    )


def downgrade() -> None:
    op.alter_column(
        "payments",
        "status",
        existing_type=sa.String(length=10),
        server_default="confirmed",
    )
