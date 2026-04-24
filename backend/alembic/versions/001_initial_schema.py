"""initial schema

Revision ID: 6ba7b8109c96
Revises:
Create Date: 2026-04-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6ba7b8109c96"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("login", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login", name="uq_users_login"),
        sa.UniqueConstraint("telegram_chat_id", name="uq_users_telegram_chat_id"),
        sa.CheckConstraint("role IN ('admin', 'client')", name="chk_users_role"),
    )

    # ── suppliers ─────────────────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("wechat_id", sa.String(100), nullable=False),
        sa.Column("document_1", sa.String(500), nullable=True),
        sa.Column("document_2", sa.String(500), nullable=True),
        sa.Column("document_3", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── projects ──────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(10), server_default="active", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["client_id"], ["users.id"], name="fk_projects_client_id"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'closed')", name="chk_projects_status"
        ),
    )
    op.create_index("idx_projects_client_id", "projects", ["client_id"])
    op.create_index("idx_projects_status", "projects", ["status"])
    op.create_index("idx_projects_created_at", "projects", ["created_at"])

    # ── project_items ─────────────────────────────────────────────────────────
    op.create_table(
        "project_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "commission", sa.Numeric(5, 2), server_default="0", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_items_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_project_items_supplier_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("quantity > 0", name="chk_project_items_quantity"),
        sa.CheckConstraint("price >= 0", name="chk_project_items_price"),
        sa.CheckConstraint("cost_price >= 0", name="chk_project_items_cost_price"),
        sa.CheckConstraint(
            "currency IN ('CNY', 'USD', 'RUB')", name="chk_project_items_currency"
        ),
    )
    op.create_index(
        "idx_project_items_project_id", "project_items", ["project_id"]
    )

    # ── project_item_requirements ─────────────────────────────────────────────
    op.create_table(
        "project_item_requirements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["project_items.id"],
            name="fk_requirements_item_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_requirements_item_id", "project_item_requirements", ["item_id"]
    )

    # ── payment_requests ──────────────────────────────────────────────────────
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("requisites", sa.Text(), nullable=True),
        sa.Column("payment_details", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_payment_requests_project_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_payment_requests_created_by",
        ),
        sa.CheckConstraint(
            "total_amount > 0", name="chk_payment_requests_amount"
        ),
        sa.CheckConstraint(
            "currency IN ('CNY', 'USD', 'RUB')",
            name="chk_payment_requests_currency",
        ),
    )
    op.create_index(
        "idx_payment_requests_project_id", "payment_requests", ["project_id"]
    )

    # ── payment_request_items ─────────────────────────────────────────────────
    op.create_table(
        "payment_request_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_request_id", sa.Integer(), nullable=False),
        sa.Column("project_item_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["payment_request_id"],
            ["payment_requests.id"],
            name="fk_pri_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_item_id"],
            ["project_items.id"],
            name="fk_pri_item_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "payment_request_id",
            "project_item_id",
            name="uq_payment_request_items",
        ),
        sa.CheckConstraint(
            "amount > 0", name="chk_payment_request_items_amount"
        ),
    )

    # ── payment_request_attachments ───────────────────────────────────────────
    op.create_table(
        "payment_request_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_request_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["payment_request_id"],
            ["payment_requests.id"],
            name="fk_attachments_request_id",
            ondelete="CASCADE",
        ),
    )

    # ── payments ──────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_request_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["payment_request_id"],
            ["payment_requests.id"],
            name="fk_payments_request_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_payments_created_by"
        ),
        sa.CheckConstraint("amount > 0", name="chk_payments_amount"),
        sa.CheckConstraint(
            "currency IN ('CNY', 'USD', 'RUB')", name="chk_payments_currency"
        ),
    )
    op.create_index("idx_payments_request_id", "payments", ["payment_request_id"])


def downgrade() -> None:
    op.drop_index("idx_payments_request_id", table_name="payments")
    op.drop_table("payments")
    op.drop_table("payment_request_attachments")
    op.drop_table("payment_request_items")
    op.drop_index(
        "idx_payment_requests_project_id", table_name="payment_requests"
    )
    op.drop_table("payment_requests")
    op.drop_index("idx_requirements_item_id", table_name="project_item_requirements")
    op.drop_table("project_item_requirements")
    op.drop_index("idx_project_items_project_id", table_name="project_items")
    op.drop_table("project_items")
    op.drop_index("idx_projects_created_at", table_name="projects")
    op.drop_index("idx_projects_status", table_name="projects")
    op.drop_index("idx_projects_client_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("suppliers")
    op.drop_table("users")
