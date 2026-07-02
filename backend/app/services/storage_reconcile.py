"""
Реконсилятор outbox репликации S3.

Проигрывает записи storage_replication_pending, когда отставший таргет вернулся:
  - op='put'    → копирует объект из живого таргета в отставший;
  - op='delete' → удаляет объект в отставшем таргете.

Успешно обработанные строки удаляются; при ошибке растёт attempts/last_error.
Работает в паре с периодическим `rclone bisync` (сайдкар reconcile/), который двусторонне
залечивает любое расхождение, даже если outbox что-то не поймал.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.storage_replication_pending import StorageReplicationPending
from app.services import storage_service

logger = logging.getLogger(__name__)


async def _copy_object(key: str, dst: storage_service.S3Target) -> bool:
    """Копирует key из любого живого таргета в dst. True при успехе."""
    body = await storage_service.get(key)  # читает с первого доступного таргета
    if body is None:
        logger.warning("reconcile put: объект %s не найден ни в одном живом таргете", key)
        return False
    async with storage_service.client(dst) as s3:
        await s3.put_object(Bucket=dst.bucket, Key=key, Body=body)
    return True


async def _delete_object(key: str, dst: storage_service.S3Target) -> bool:
    async with storage_service.client(dst, read_timeout=10) as s3:
        await s3.delete_object(Bucket=dst.bucket, Key=key)
    return True


async def reconcile_once(batch: int = 200) -> dict:
    """
    Обрабатывает до `batch` записей outbox. Возвращает статистику.
    Идемпотентно — можно звать по cron/эндпоинту сколько угодно.
    """
    targets = {t.name: t for t in storage_service.file_targets()}
    done = 0
    failed = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(StorageReplicationPending)
                .order_by(StorageReplicationPending.id)
                .limit(batch)
            )
        ).scalars().all()

        for row in rows:
            dst = targets.get(row.target)
            if dst is None:
                # Таргет больше не сконфигурирован — снимаем запись, чтобы не копить.
                await session.delete(row)
                skipped += 1
                continue
            try:
                if row.op == "put":
                    ok = await _copy_object(row.key, dst)
                elif row.op == "delete":
                    ok = await _delete_object(row.key, dst)
                else:
                    ok = False
                if ok:
                    await session.delete(row)
                    done += 1
                else:
                    row.attempts += 1
                    row.last_error = "reconcile: источник недоступен/не найден"
                    failed += 1
            except Exception as e:  # noqa: BLE001
                row.attempts += 1
                row.last_error = str(e)[:512]
                failed += 1
                logger.warning("reconcile %s %s→%s не удался: %s", row.op, row.key, row.target, e)

        await session.commit()

    result = {"done": done, "failed": failed, "skipped": skipped, "processed": len(rows)}
    logger.info("reconcile_once: %s", result)
    return result
