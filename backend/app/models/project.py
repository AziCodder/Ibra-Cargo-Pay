from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'closed')", name="chk_projects_status"),
        Index("idx_projects_client_id", "client_id"),
        Index("idx_projects_status", "status"),
        Index("idx_projects_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        server_default=text("nextval('projects_number_seq')"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(10), server_default="active", nullable=False)
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
    client: Mapped[User | None] = relationship(
        "User", back_populates="projects", foreign_keys=[client_id]
    )
    items: Mapped[list[ProjectItem]] = relationship(
        "ProjectItem", back_populates="project", cascade="all, delete-orphan"
    )
    payment_requests: Mapped[list[PaymentRequest]] = relationship(
        "PaymentRequest", back_populates="project"
    )
