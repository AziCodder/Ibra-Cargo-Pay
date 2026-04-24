from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PaymentRequestComment(Base):
    __tablename__ = "payment_request_comments"
    __table_args__ = (
        Index("idx_prc_request_created", "payment_request_id", "created_at"),
        Index("idx_prc_author", "author_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_request_id: Mapped[int] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    payment_request: Mapped[PaymentRequest] = relationship(
        "PaymentRequest", back_populates="comments"
    )
    author: Mapped[User] = relationship(
        "User",
        back_populates="authored_comments",
        foreign_keys=[author_id],
    )
