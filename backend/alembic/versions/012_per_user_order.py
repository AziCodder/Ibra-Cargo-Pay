"""Per-user ordering: project_item_orders, project_orders

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-27

"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_item_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_item_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_item_id"], ["project_items.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "user_id", "project_item_id", name="uq_project_item_order_user_item"
        ),
    )
    op.create_index(
        "idx_project_item_orders_user", "project_item_orders", ["user_id"]
    )

    op.create_table(
        "project_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "project_id", name="uq_project_order_user_project"
        ),
    )
    op.create_index("idx_project_orders_user", "project_orders", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_project_orders_user", table_name="project_orders")
    op.drop_table("project_orders")
    op.drop_index("idx_project_item_orders_user", table_name="project_item_orders")
    op.drop_table("project_item_orders")
