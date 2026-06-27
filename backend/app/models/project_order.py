from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProjectOrder(Base):
    """Персональный порядок проектов для конкретного пользователя.

    Один пользователь — своя перестановка карточек проектов; у других не меняется.
    """

    __tablename__ = "project_orders"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "project_id", name="uq_project_order_user_project"
        ),
        Index("idx_project_orders_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
