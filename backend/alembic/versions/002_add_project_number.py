"""add project_number to projects

Revision ID: a3f1c2d4e5b6
Revises: 6ba7b8109c96
Create Date: 2026-04-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f1c2d4e5b6"
down_revision: Union[str, None] = "6ba7b8109c96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS projects_number_seq START 1")
    op.add_column(
        "projects",
        sa.Column(
            "project_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("nextval('projects_number_seq')"),
        ),
    )
    op.create_unique_constraint("uq_projects_project_number", "projects", ["project_number"])
    op.execute("ALTER SEQUENCE projects_number_seq OWNED BY projects.project_number")


def downgrade() -> None:
    op.drop_constraint("uq_projects_project_number", "projects", type_="unique")
    op.drop_column("projects", "project_number")
    # sequence is dropped automatically due to OWNED BY
