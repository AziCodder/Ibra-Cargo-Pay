from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StorageReplicationPending(Base):
    """
    Outbox для догоняющей репликации S3.

    Когда dual-write не смог записать/удалить объект в один из таргетов (таргет временно
    недоступен), сюда падает запись (key, op, target). Фоновый реконсилятор
    (storage_reconcile) позже проигрывает эти операции, когда таргет вернулся:
      - op='put'    → копирует key из живого таргета в отставший;
      - op='delete' → удаляет key в отставшем таргете.

    Тело файла тут не хранится — при ретрае оно берётся из здорового таргета.
    """

    __tablename__ = "storage_replication_pending"
    __table_args__ = (
        Index("idx_storage_repl_pending_target", "target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(1024), nullable=False)
    op: Mapped[str] = mapped_column(String(16), nullable=False)  # put | delete
    target: Mapped[str] = mapped_column(String(32), nullable=False)  # primary | secondary
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
