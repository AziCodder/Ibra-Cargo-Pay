"""Add payment_date to payments table

Revision ID: e8f5a1b2c3d4
Revises: d7e4f8a9b0c1
Create Date: 2026-05-12

"""

from alembic import op
import sqlalchemy as sa

revision = "e8f5a1b2c3d4"
down_revision = "d7e4f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("payment_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "payment_date")
