from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PaymentRequestItem(Base):
    __tablename__ = "payment_request_items"
    __table_args__ = (
        UniqueConstraint(
            "payment_request_id",
            "project_item_id",
            name="uq_payment_request_items",
        ),
        CheckConstraint("amount > 0", name="chk_payment_request_items_amount"),
        Index("idx_payment_request_items_request_id", "payment_request_id"),
        Index("idx_payment_request_items_item_id", "project_item_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_request_id: Mapped[int] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="CASCADE"), nullable=False
    )
    project_item_id: Mapped[int] = mapped_column(
        ForeignKey("project_items.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Relationships
    payment_request: Mapped[PaymentRequest] = relationship(
        "PaymentRequest", back_populates="items"
    )
    project_item: Mapped[ProjectItem] = relationship(
        "ProjectItem", back_populates="payment_request_items"
    )
