from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_payments_amount"),
        CheckConstraint(
            "currency IN ('CNY', 'USD', 'RUB')", name="chk_payments_currency"
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="chk_payments_status",
        ),
        Index("idx_payments_request_id", "payment_request_id"),
        Index("idx_payments_created_by", "created_by"),
        Index("idx_payments_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_request_id: Mapped[int] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_name: Mapped[str | None] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Статус подтверждения: pending (ожидает), confirmed (подтверждён), rejected (отклонён)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending", server_default="confirmed"
    )
    confirmed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    payment_request: Mapped[PaymentRequest] = relationship(
        "PaymentRequest", back_populates="payments"
    )
    creator: Mapped[User] = relationship(
        "User",
        back_populates="created_payments",
        foreign_keys=[created_by],
    )
    confirmer: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[confirmed_by],
    )
