"""security and integrity fixes

Add missing updated_at columns, indexes, change FK from CASCADE to RESTRICT.

Revision ID: b4c2d5e6f7a8
Revises: a3f1c2d4e5b6
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c2d5e6f7a8"
down_revision: Union[str, None] = "a3f1c2d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add updated_at to payments ---
    op.add_column(
        "payments",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Add updated_at to project_item_requirements ---
    op.add_column(
        "project_item_requirements",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Add missing indexes ---
    op.create_index(
        "idx_payments_created_by", "payments", ["created_by"]
    )
    op.create_index(
        "idx_payment_requests_created_by", "payment_requests", ["created_by"]
    )
    op.create_index(
        "idx_payment_request_items_request_id",
        "payment_request_items",
        ["payment_request_id"],
    )
    op.create_index(
        "idx_payment_request_items_item_id",
        "payment_request_items",
        ["project_item_id"],
    )

    # --- Change FK on payment_request_items.project_item_id: CASCADE -> RESTRICT ---
    op.drop_constraint(
        "fk_pri_item_id",
        "payment_request_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_pri_item_id",
        "payment_request_items",
        "project_items",
        ["project_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Revert FK to CASCADE
    op.drop_constraint(
        "fk_pri_item_id",
        "payment_request_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_pri_item_id",
        "payment_request_items",
        "project_items",
        ["project_item_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop indexes
    op.drop_index("idx_payment_request_items_item_id", "payment_request_items")
    op.drop_index("idx_payment_request_items_request_id", "payment_request_items")
    op.drop_index("idx_payment_requests_created_by", "payment_requests")
    op.drop_index("idx_payments_created_by", "payments")

    # Drop updated_at columns
    op.drop_column("project_item_requirements", "updated_at")
    op.drop_column("payments", "updated_at")
