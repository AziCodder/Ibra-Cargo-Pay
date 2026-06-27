from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProjectItem(Base):
    __tablename__ = "project_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_project_items_quantity"),
        CheckConstraint("price >= 0", name="chk_project_items_price"),
        CheckConstraint(
            "cost_price IS NULL OR cost_price >= 0",
            name="chk_project_items_cost_price",
        ),
        CheckConstraint(
            "currency IN ('CNY', 'USD', 'RUB')", name="chk_project_items_currency"
        ),
        Index("idx_project_items_project_id", "project_id"),
        Index("idx_project_items_sort", "project_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL")
    )
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    commission: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=False
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    shared_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship("Project", back_populates="items")
    supplier: Mapped[Supplier | None] = relationship("Supplier", back_populates="items")
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])
    requirements: Mapped[list[ProjectItemRequirement]] = relationship(
        "ProjectItemRequirement", back_populates="item", cascade="all, delete-orphan"
    )
    payment_request_items: Mapped[list[PaymentRequestItem]] = relationship(
        "PaymentRequestItem", back_populates="project_item"
    )
