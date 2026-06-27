from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProjectItemOrder(Base):
    """Персональный порядок позиций номенклатуры для конкретного пользователя.

    Один пользователь — своя перестановка; у других порядок не меняется.
    """

    __tablename__ = "project_item_orders"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "project_item_id", name="uq_project_item_order_user_item"
        ),
        Index("idx_project_item_orders_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_item_id: Mapped[int] = mapped_column(
        ForeignKey("project_items.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
