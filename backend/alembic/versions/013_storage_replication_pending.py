"""Storage replication outbox: storage_replication_pending

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-02

"""

from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storage_replication_pending",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=1024), nullable=False),
        sa.Column("op", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_storage_repl_pending_target", "storage_replication_pending", ["target"]
    )


def downgrade() -> None:
    op.drop_index(
        "idx_storage_repl_pending_target", table_name="storage_replication_pending"
    )
    op.drop_table("storage_replication_pending")
