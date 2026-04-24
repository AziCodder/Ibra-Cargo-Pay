from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'client')", name="chk_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
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
    projects: Mapped[list[Project]] = relationship(
        "Project", back_populates="client", foreign_keys="[Project.client_id]"
    )
    created_payment_requests: Mapped[list[PaymentRequest]] = relationship(
        "PaymentRequest", back_populates="creator", foreign_keys="[PaymentRequest.created_by]"
    )
    created_payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="creator", foreign_keys="[Payment.created_by]"
    )
    audit_entries: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="user", foreign_keys="[AuditLog.user_id]"
    )
    authored_comments: Mapped[list[PaymentRequestComment]] = relationship(
        "PaymentRequestComment",
        back_populates="author",
        foreign_keys="[PaymentRequestComment.author_id]",
    )
