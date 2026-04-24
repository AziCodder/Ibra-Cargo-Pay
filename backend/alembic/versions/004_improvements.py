"""improvements: due_date, priority, audit log, comments

Adds:
- payment_requests.due_date (nullable date)
- payment_requests.priority (urgent / normal / deferred)
- audit_log table
- payment_request_comments table

Revision ID: c5d3e6f7a8b9
Revises: b4c2d5e6f7a8
Create Date: 2026-04-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5d3e6f7a8b9"
down_revision: Union[str, None] = "b4c2d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- payment_requests: due_date + priority ---
    op.add_column(
        "payment_requests",
        sa.Column("due_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "payment_requests",
        sa.Column(
            "priority",
            sa.String(length=10),
            nullable=False,
            server_default="normal",
        ),
    )
    op.create_check_constraint(
        "chk_payment_requests_priority",
        "payment_requests",
        "priority IN ('urgent', 'normal', 'deferred')",
    )
    op.create_index(
        "idx_payment_requests_due_date",
        "payment_requests",
        ["due_date"],
    )
    op.create_index(
        "idx_payment_requests_priority",
        "payment_requests",
        ["priority"],
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'deleted')",
            name="chk_audit_log_action",
        ),
    )
    op.create_index(
        "idx_audit_log_entity",
        "audit_log",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "idx_audit_log_user_id",
        "audit_log",
        ["user_id"],
    )
    op.create_index(
        "idx_audit_log_created_at",
        "audit_log",
        [sa.text("created_at DESC")],
    )

    # --- payment_request_comments ---
    op.create_table(
        "payment_request_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payment_request_id",
            sa.Integer(),
            sa.ForeignKey("payment_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_prc_request_created",
        "payment_request_comments",
        ["payment_request_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_prc_author",
        "payment_request_comments",
        ["author_id"],
    )


def downgrade() -> None:
    # --- comments ---
    op.drop_index("idx_prc_author", "payment_request_comments")
    op.drop_index("idx_prc_request_created", "payment_request_comments")
    op.drop_table("payment_request_comments")

    # --- audit_log ---
    op.drop_index("idx_audit_log_created_at", "audit_log")
    op.drop_index("idx_audit_log_user_id", "audit_log")
    op.drop_index("idx_audit_log_entity", "audit_log")
    op.drop_table("audit_log")

    # --- payment_requests: priority + due_date ---
    op.drop_index("idx_payment_requests_priority", "payment_requests")
    op.drop_index("idx_payment_requests_due_date", "payment_requests")
    op.drop_constraint(
        "chk_payment_requests_priority",
        "payment_requests",
        type_="check",
    )
    op.drop_column("payment_requests", "priority")
    op.drop_column("payment_requests", "due_date")
