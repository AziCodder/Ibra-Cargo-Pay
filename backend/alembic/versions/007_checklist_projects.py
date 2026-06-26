"""Checklist: nullable projects.client_id

Revision ID: f9a2b3c4d5e6
Revises: e8f5a1b2c3d4
Create Date: 2026-06-27

"""

from alembic import op
import sqlalchemy as sa

revision = "f9a2b3c4d5e6"
down_revision = "e8f5a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "projects",
        "client_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.execute(sa.text("UPDATE projects SET client_id = NULL"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE projects SET client_id = (SELECT id FROM users WHERE role = 'client' LIMIT 1) "
            "WHERE client_id IS NULL"
        )
    )
    op.alter_column(
        "projects",
        "client_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
