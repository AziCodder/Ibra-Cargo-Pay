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


class PaymentRequest(Base):
    __tablename__ = "payment_requests"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="chk_payment_requests_amount"),
        CheckConstraint(
            "currency IN ('CNY', 'USD', 'RUB')", name="chk_payment_requests_currency"
        ),
        CheckConstraint(
            "priority IN ('urgent', 'normal', 'deferred')",
            name="chk_payment_requests_priority",
        ),
        Index("idx_payment_requests_project_id", "project_id"),
        Index("idx_payment_requests_created_by", "created_by"),
        Index("idx_payment_requests_due_date", "due_date"),
        Index("idx_payment_requests_priority", "priority"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    requisites: Mapped[str | None] = mapped_column(Text)
    payment_details: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="normal"
    )
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
    project: Mapped[Project] = relationship("Project", back_populates="payment_requests")
    creator: Mapped[User] = relationship(
        "User",
        back_populates="created_payment_requests",
        foreign_keys=[created_by],
    )
    items: Mapped[list[PaymentRequestItem]] = relationship(
        "PaymentRequestItem", back_populates="payment_request", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[PaymentRequestAttachment]] = relationship(
        "PaymentRequestAttachment",
        back_populates="payment_request",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="payment_request"
    )
    comments: Mapped[list[PaymentRequestComment]] = relationship(
        "PaymentRequestComment",
        back_populates="payment_request",
        cascade="all, delete-orphan",
    )
