"""Checklist: projects.sort_order для ручного порядка проектов

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-27

"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    # Бэкофилл: начальный порядок = по дате создания (старые сверху).
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC) - 1 AS rn
                FROM projects
            )
            UPDATE projects
            SET sort_order = ranked.rn
            FROM ranked
            WHERE projects.id = ranked.id
            """
        )
    )
    op.create_index("idx_projects_sort_order", "projects", ["sort_order"])


def downgrade() -> None:
    op.drop_index("idx_projects_sort_order", table_name="projects")
    op.drop_column("projects", "sort_order")
