"""Checklist: project_items shared_access, created_by, sort_order

Revision ID: a1b2c3d4e5f6
Revises: f9a2b3c4d5e6
Create Date: 2026-06-27

"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f9a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_items", sa.Column("created_by", sa.Integer(), nullable=True))
    op.add_column(
        "project_items",
        sa.Column("shared_access", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "project_items",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        sa.text(
            "UPDATE project_items SET created_by = "
            "(SELECT id FROM users WHERE role = 'admin' LIMIT 1) "
            "WHERE created_by IS NULL"
        )
    )

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY id) - 1 AS rn
                FROM project_items
            )
            UPDATE project_items
            SET sort_order = ranked.rn
            FROM ranked
            WHERE project_items.id = ranked.id
            """
        )
    )

    op.alter_column("project_items", "created_by", nullable=False)
    op.create_foreign_key(
        "fk_project_items_created_by_users",
        "project_items",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_index(
        "idx_project_items_sort",
        "project_items",
        ["project_id", "sort_order"],
    )
    op.alter_column(
        "project_items",
        "cost_price",
        existing_type=sa.Numeric(14, 2),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE project_items SET cost_price = price WHERE cost_price IS NULL"
        )
    )
    op.alter_column(
        "project_items",
        "cost_price",
        existing_type=sa.Numeric(14, 2),
        nullable=False,
    )
    op.drop_index("idx_project_items_sort", table_name="project_items")
    op.drop_constraint("fk_project_items_created_by_users", "project_items", type_="foreignkey")
    op.drop_column("project_items", "sort_order")
    op.drop_column("project_items", "shared_access")
    op.drop_column("project_items", "created_by")
