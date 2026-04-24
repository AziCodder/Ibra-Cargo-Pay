"""payment approval workflow: status, confirmed_by, confirmed_at, rejection_reason

Adds:
- payments.status (pending / confirmed / rejected), default 'pending'
- payments.confirmed_by (FK -> users.id, nullable)
- payments.confirmed_at (timestamptz, nullable)
- payments.rejection_reason (text, nullable)

Логика:
- Клиент создаёт платёж -> status='pending'
- Админ подтверждает -> status='confirmed', confirmed_by=admin, confirmed_at=now()
- Админ отклоняет -> status='rejected' + rejection_reason (обязательно)
- remaining_amount учитывает ТОЛЬКО 'confirmed' платежи

Revision ID: d7e4f8a9b0c1
Revises: c5d3e6f7a8b9
Create Date: 2026-04-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d7e4f8a9b0c1"
down_revision: Union[str, None] = "c5d3e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # status с default, чтобы существующие записи получили 'confirmed'
    # (старые платежи считаем подтверждёнными, т.к. логика подтверждения — новая)
    op.add_column(
        "payments",
        sa.Column(
            "status",
            sa.String(length=10),
            nullable=False,
            server_default="confirmed",
        ),
    )
    # После установки server_default переключаем default для новых записей на 'pending'
    # (но server_default в БД оставим 'confirmed' для обратной совместимости,
    # модель SQLAlchemy использует default='pending')

    op.add_column(
        "payments",
        sa.Column(
            "confirmed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )

    op.create_check_constraint(
        "chk_payments_status",
        "payments",
        "status IN ('pending', 'confirmed', 'rejected')",
    )
    op.create_index("idx_payments_status", "payments", ["status"])

    # Существующие платежи — помечаем confirmed_at = created_at и confirmed_by = created_by
    op.execute(
        "UPDATE payments SET confirmed_at = created_at, confirmed_by = created_by "
        "WHERE status = 'confirmed'"
    )


def downgrade() -> None:
    op.drop_index("idx_payments_status", "payments")
    op.drop_constraint("chk_payments_status", "payments", type_="check")
    op.drop_column("payments", "rejection_reason")
    op.drop_column("payments", "confirmed_at")
    op.drop_column("payments", "confirmed_by")
    op.drop_column("payments", "status")
