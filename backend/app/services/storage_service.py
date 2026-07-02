"""
Слой S3-хранилища с записью в несколько таргетов (dual-write).

Идея: все записи файлов и дампов БД идут во ВСЕ настроенные таргеты сразу
(PRIMARY = S3_*, SECONDARY = S3_SECONDARY_*). Запись считается успешной, если прошла
хотя бы в один таргет. Для таргетов, куда запись/удаление не удалось, кладём запись в
outbox (storage_replication_pending) — фоновый реконсилятор (storage_reconcile) догонит
их, когда таргет вернётся. Плюс периодический `rclone bisync` (сайдкар reconcile/)
двусторонне залечивает любое расхождение.

Чтение и presigned URL — с первого доступного таргета (PRIMARY → SECONDARY).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S3Target:
    name: str  # "primary" | "secondary"
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region: str
    bucket: str

    @property
    def configured(self) -> bool:
        return bool(
            self.endpoint_url
            and self.access_key_id
            and self.secret_access_key
            and self.bucket
        )


def file_targets() -> list[S3Target]:
    """Список настроенных таргетов для файлов (PRIMARY + SECONDARY, если заданы)."""
    from app.core.config import settings

    targets: list[S3Target] = []
    primary = S3Target(
        name="primary",
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        region=settings.s3_region,
        bucket=settings.s3_bucket_name,
    )
    if primary.configured:
        targets.append(primary)

    secondary = S3Target(
        name="secondary",
        endpoint_url=settings.s3_secondary_endpoint_url,
        access_key_id=settings.s3_secondary_access_key_id,
        secret_access_key=settings.s3_secondary_secret_access_key,
        region=settings.s3_secondary_region or "us-1",
        bucket=settings.s3_secondary_bucket or settings.s3_bucket_name,
    )
    if secondary.configured:
        targets.append(secondary)

    return targets


def target_by_name(name: str, targets: list[S3Target] | None = None) -> S3Target | None:
    for t in (targets or file_targets()):
        if t.name == name:
            return t
    return None


def _client_config(read_timeout: int = 15):
    """Единый конфиг S3-клиента (S3-совместимые: signature v4, path-style)."""
    from botocore.config import Config as BotocoreConfig

    return BotocoreConfig(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        connect_timeout=5,
        read_timeout=read_timeout,
        # 2 попытки (standard): переживаем единичный сетевой сбой без похода в outbox.
        retries={"max_attempts": 2, "mode": "standard"},
    )


@asynccontextmanager
async def client(target: S3Target, read_timeout: int = 15):
    """Асинхронный S3-клиент для конкретного таргета."""
    import aioboto3

    session = aioboto3.Session(
        aws_access_key_id=target.access_key_id,
        aws_secret_access_key=target.secret_access_key,
        region_name=target.region,
    )
    async with session.client(
        "s3", endpoint_url=target.endpoint_url, config=_client_config(read_timeout)
    ) as s3:
        yield s3


async def _enqueue_outbox(key: str, op: str, target_name: str, error: str) -> None:
    """Best-effort запись в outbox для последующего ретрая. Не роняет основную операцию."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.storage_replication_pending import StorageReplicationPending

        async with AsyncSessionLocal() as session:
            session.add(
                StorageReplicationPending(
                    key=key, op=op, target=target_name, last_error=error[:512]
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Не удалось записать в outbox репликации: %s %s→%s", op, key, target_name)


async def _put_one(target: S3Target, key: str, body: bytes, content_type: str | None) -> None:
    async with client(target) as s3:
        kwargs = {"Bucket": target.bucket, "Key": key, "Body": body}
        if content_type:
            kwargs["ContentType"] = content_type
        await s3.put_object(**kwargs)


async def _delete_one(target: S3Target, key: str) -> None:
    async with client(target, read_timeout=10) as s3:
        await s3.delete_object(Bucket=target.bucket, Key=key)


async def put(key: str, body: bytes, content_type: str | None = None) -> None:
    """
    Пишет объект во все настроенные таргеты сразу. Успех, если записалось хотя бы в один.
    Для упавших таргетов кладёт запись в outbox. Бросает RuntimeError, только если не
    записалось НИ В ОДИН таргет.
    """
    targets = file_targets()
    if not targets:
        logger.warning("Нет настроенных S3-таргетов, объект не сохранён: %s", key)
        raise RuntimeError(f"S3 не настроен, объект не сохранён: {key}")

    results = await asyncio.gather(
        *[_put_one(t, key, body, content_type) for t in targets],
        return_exceptions=True,
    )

    ok = 0
    for target, res in zip(targets, results):
        if isinstance(res, Exception):
            logger.error("put в таргет '%s' не удался (%s): %s", target.name, key, res)
            await _enqueue_outbox(key, "put", target.name, str(res))
        else:
            ok += 1

    if ok == 0:
        raise RuntimeError(f"Не удалось записать объект ни в один S3-таргет: {key}")


async def delete(key: str) -> None:
    """Удаляет объект во всех таргетах. Упавшие → outbox. Ошибки не бросает (best-effort)."""
    targets = file_targets()
    if not targets:
        return

    results = await asyncio.gather(
        *[_delete_one(t, key) for t in targets], return_exceptions=True
    )
    for target, res in zip(targets, results):
        if isinstance(res, Exception):
            logger.error("delete в таргете '%s' не удался (%s): %s", target.name, key, res)
            await _enqueue_outbox(key, "delete", target.name, str(res))


async def get(key: str) -> bytes | None:
    """Читает объект с первого доступного таргета (PRIMARY → SECONDARY). None если нигде нет."""
    targets = file_targets()
    for target in targets:
        try:
            async with client(target) as s3:
                resp = await s3.get_object(Bucket=target.bucket, Key=key)
                async with resp["Body"] as stream:
                    return await stream.read()
        except Exception as e:
            logger.warning("get из таргета '%s' не удался (%s): %s", target.name, key, e)
            continue
    return None


async def presigned(key: str, expires_in: int = 3600) -> str | None:
    """Presigned URL с первого доступного таргета. None если ни один не отдал."""
    targets = file_targets()
    for target in targets:
        try:
            async with client(target, read_timeout=10) as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": target.bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
        except Exception as e:
            logger.warning("presigned из таргета '%s' не удался (%s): %s", target.name, key, e)
            continue
    return None
