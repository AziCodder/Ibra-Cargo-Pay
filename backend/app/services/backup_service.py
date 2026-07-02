"""
Сервис резервного копирования базы данных в S3-совместимое хранилище.

Логика: pg_dump --format=custom -Z 9 в память → put_object в backup-бакет
→ retention (удаление объектов старше BACKUP_RETENTION_DAYS).
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)


class BackupConfigError(RuntimeError):
    """Конфигурация бэкапов неполная (нет S3 или backup_s3_bucket)."""


class BackupExecutionError(RuntimeError):
    """pg_dump или загрузка в S3 завершились ошибкой."""


class BackupNotFoundError(RuntimeError):
    """Запрошенный для восстановления ключ не найден / недопустим."""


def _backup_creds() -> dict[str, str]:
    """Возвращает креды для backup-бакета. Fallback на основные S3_* при пустых backup-полях."""
    return {
        "endpoint_url": settings.backup_s3_endpoint_url or settings.s3_endpoint_url,
        "access_key_id": settings.backup_s3_access_key_id or settings.s3_access_key_id,
        "secret_access_key": settings.backup_s3_secret_access_key
        or settings.s3_secret_access_key,
        "region": settings.backup_s3_region or settings.s3_region,
    }


def _is_backup_configured() -> bool:
    c = _backup_creds()
    return bool(
        c["endpoint_url"]
        and c["access_key_id"]
        and c["secret_access_key"]
        and settings.backup_s3_bucket
    )


def _parse_db_url() -> dict[str, str]:
    """DATABASE_URL → dict для pg_dump (host, port, user, password, dbname)."""
    raw = settings.database_url
    # postgresql+asyncpg://user:pass@host:5432/db → postgresql://...
    if "+asyncpg" in raw:
        raw = raw.replace("+asyncpg", "")
    parsed = urlparse(raw)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/").lstrip("/") or "postgres",
    }


def _backup_key(now: datetime) -> str:
    prefix = settings.backup_s3_prefix
    if not prefix.endswith("/"):
        prefix += "/"
    return (
        f"{prefix}{now:%Y/%m}/dump_{now:%Y%m%d_%H%M%S}Z.dump"
    )


async def _run_pg_dump(db: dict[str, str]) -> bytes:
    """Запускает pg_dump --format=custom -Z 9 и возвращает байты дампа."""
    cmd = [
        "pg_dump",
        "--format=custom",
        "--compress=9",
        "--no-owner",
        "--no-privileges",
        "-h", db["host"],
        "-p", db["port"],
        "-U", db["user"],
        "-d", db["dbname"],
    ]
    env = {
        "PGPASSWORD": db["password"],
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }
    logger.info("Запуск pg_dump для %s@%s/%s", db["user"], db["host"], db["dbname"])
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = (stderr or b"").decode(errors="replace").strip()
        raise BackupExecutionError(f"pg_dump exit={proc.returncode}: {msg}")
    if not stdout:
        raise BackupExecutionError("pg_dump вернул пустой результат")
    return stdout


def _backup_targets() -> list:
    """
    Таргеты для дампов БД (dual-write). Дамп заливается в КАЖДЫЙ.
      1. 'storj'  — выделенный backup-бакет (BACKUP_S3_*, напр. Storj) — канонический.
      2. 'main'   — основной S3 (S3_*, напр. Hostkey), дампы под тем же префиксом
                    в основном бакете. Вторая физическая копия у другого провайдера.
    Дубли (одинаковый endpoint+bucket) отсекаются.
    """
    from app.services.storage_service import S3Target

    targets: list[S3Target] = []
    c = _backup_creds()
    if c["endpoint_url"] and c["access_key_id"] and c["secret_access_key"] and settings.backup_s3_bucket:
        targets.append(
            S3Target(
                name="storj",
                endpoint_url=c["endpoint_url"],
                access_key_id=c["access_key_id"],
                secret_access_key=c["secret_access_key"],
                region=c["region"] or "us-1",
                bucket=settings.backup_s3_bucket,
            )
        )

    if (
        settings.s3_endpoint_url
        and settings.s3_access_key_id
        and settings.s3_secret_access_key
        and settings.s3_bucket_name
    ):
        dup = any(
            t.endpoint_url == settings.s3_endpoint_url and t.bucket == settings.s3_bucket_name
            for t in targets
        )
        if not dup:
            targets.append(
                S3Target(
                    name="main",
                    endpoint_url=settings.s3_endpoint_url,
                    access_key_id=settings.s3_access_key_id,
                    secret_access_key=settings.s3_secret_access_key,
                    region=settings.s3_region,
                    bucket=settings.s3_bucket_name,
                )
            )

    return targets


async def _upload(key: str, body: bytes) -> None:
    """Заливает дамп во ВСЕ backup-таргеты. Успех, если хотя бы один принял."""
    from app.services import storage_service

    targets = _backup_targets()
    if not targets:
        raise BackupExecutionError("Нет настроенных backup-таргетов для загрузки дампа")

    async def _one(t):
        async with storage_service.client(t, read_timeout=300) as s3:
            await s3.put_object(
                Bucket=t.bucket,
                Key=key,
                Body=body,
                ContentType="application/octet-stream",
            )

    results = await asyncio.gather(*[_one(t) for t in targets], return_exceptions=True)
    ok = 0
    for t, r in zip(targets, results):
        if isinstance(r, Exception):
            logger.error("Загрузка дампа в таргет '%s' не удалась: %s", t.name, r)
        else:
            ok += 1
    if ok == 0:
        raise BackupExecutionError("Не удалось залить дамп ни в один backup-таргет")


async def _apply_retention() -> int:
    """Удаляет дампы старше backup_retention_days во ВСЕХ таргетах. Возвращает число удалённых."""
    if settings.backup_retention_days <= 0:
        return 0
    from app.services import storage_service

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.backup_retention_days)
    prefix = settings.backup_s3_prefix
    if not prefix.endswith("/"):
        prefix += "/"

    deleted = 0
    for target in _backup_targets():
        try:
            async with storage_service.client(target, read_timeout=60) as s3:
                continuation: str | None = None
                while True:
                    kwargs = {"Bucket": target.bucket, "Prefix": prefix}
                    if continuation:
                        kwargs["ContinuationToken"] = continuation
                    resp = await s3.list_objects_v2(**kwargs)
                    old_keys = [
                        {"Key": obj["Key"]}
                        for obj in resp.get("Contents", [])
                        if obj.get("LastModified") and obj["LastModified"] < cutoff
                    ]
                    if old_keys:
                        # delete_objects поддерживает до 1000 ключей за вызов
                        for i in range(0, len(old_keys), 1000):
                            chunk = old_keys[i : i + 1000]
                            await s3.delete_objects(
                                Bucket=target.bucket,
                                Delete={"Objects": chunk, "Quiet": True},
                            )
                            deleted += len(chunk)
                    if not resp.get("IsTruncated"):
                        break
                    continuation = resp.get("NextContinuationToken")
        except Exception:
            logger.exception("Retention для таргета '%s' не выполнен", target.name)
    return deleted


async def list_backups(limit: int = 100) -> list[dict]:
    """Список бэкапов в бакете (последние сверху). Только метаданные."""
    if not _is_backup_configured():
        return []
    from app.services import storage_service

    prefix = settings.backup_s3_prefix
    if not prefix.endswith("/"):
        prefix += "/"

    # Ключи одинаковы во всех таргетах — листим с первого доступного (fallback по таргетам).
    for target in _backup_targets():
        try:
            items: list[dict] = []
            async with storage_service.client(target, read_timeout=60) as s3:
                continuation: str | None = None
                while True:
                    kwargs = {"Bucket": target.bucket, "Prefix": prefix}
                    if continuation:
                        kwargs["ContinuationToken"] = continuation
                    resp = await s3.list_objects_v2(**kwargs)
                    for obj in resp.get("Contents", []):
                        items.append({
                            "key": obj["Key"],
                            "size_bytes": int(obj.get("Size") or 0),
                            "last_modified": obj["LastModified"].isoformat()
                            if obj.get("LastModified") else None,
                        })
                    if not resp.get("IsTruncated"):
                        break
                    continuation = resp.get("NextContinuationToken")
            items.sort(key=lambda x: x["last_modified"] or "", reverse=True)
            return items[:limit]
        except Exception:
            logger.warning("Не удалось получить список бэкапов из таргета '%s'", target.name)
            continue
    return []


async def _send_backup_to_telegram(dump_bytes: bytes, key: str) -> None:
    """Отправляет файл бэкапа в Telegram. Молча пропускает если не настроено."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_notify_chat_id
    if not token or not chat_id:
        return

    import httpx

    filename = key.split("/")[-1]
    size_mb = len(dump_bytes) / 1048576
    tg_url = f"https://api.telegram.org/bot{token}"

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if len(dump_bytes) > 50 * 1024 * 1024:
                # Файл > 50 МБ — Telegram не примет, шлём только уведомление
                await client.post(f"{tg_url}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": (
                        f"✅ <b>Бэкап БД выполнен</b>\n"
                        f"📁 <code>{filename}</code>\n"
                        f"💾 {size_mb:.2f} МБ (файл слишком большой для отправки в Telegram)"
                    ),
                    "parse_mode": "HTML",
                })
            else:
                await client.post(f"{tg_url}/sendDocument", data={"chat_id": chat_id}, files={
                    "document": (filename, dump_bytes, "application/octet-stream"),
                    "caption": (
                        None,
                        f"✅ <b>Бэкап БД</b>\n📁 {filename}\n💾 {size_mb:.2f} МБ",
                    ),
                    "parse_mode": (None, "HTML"),
                })
    except Exception:
        logger.exception("Не удалось отправить бэкап в Telegram")


async def run_backup(notify: bool = True) -> dict:
    """
    Делает дамп БД и кладёт в S3. Возвращает метаданные.
    Бросает BackupConfigError / BackupExecutionError при проблемах.

    notify=False — не отправлять файл в Telegram (для почасовых тихих бэкапов,
    чтобы не заспамить чат; ежедневный запуск шлёт как раньше).
    """
    if not _is_backup_configured():
        raise BackupConfigError(
            "Бэкапы не настроены. Задайте S3_* и BACKUP_S3_BUCKET в .env"
        )

    started = datetime.now(timezone.utc)
    db = _parse_db_url()
    dump_bytes = await _run_pg_dump(db)

    key = _backup_key(started)
    try:
        await _upload(key, dump_bytes)
    except Exception as e:
        logger.exception("Ошибка загрузки бэкапа в S3")
        raise BackupExecutionError(f"Не удалось загрузить бэкап в S3: {e}") from e

    deleted = 0
    try:
        deleted = await _apply_retention()
    except Exception:
        logger.exception("Ошибка retention (бэкап создан, но старые не удалены)")

    if notify:
        await _send_backup_to_telegram(dump_bytes, key)

    finished = datetime.now(timezone.utc)
    return {
        "key": key,
        "size_bytes": len(dump_bytes),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "deleted_old_count": deleted,
        "bucket": settings.backup_s3_bucket,
    }


# ─── Восстановление БД из бэкапа ────────────────────────────────────────────────


def _normalized_prefix() -> str:
    prefix = settings.backup_s3_prefix
    return prefix if prefix.endswith("/") else prefix + "/"


async def _download_dump(key: str) -> bytes:
    """
    Скачивает дамп по ключу, перебирая таргеты по очереди (если один провайдер недоступен —
    берём копию с другого). BackupNotFoundError только если ключа нет НИ В ОДНОМ таргете.
    """
    from botocore.exceptions import ClientError

    from app.services import storage_service

    targets = _backup_targets()
    last_exec_error: Exception | None = None
    not_found_everywhere = True

    for target in targets:
        try:
            async with storage_service.client(target, read_timeout=300) as s3:
                resp = await s3.get_object(Bucket=target.bucket, Key=key)
                async with resp["Body"] as stream:
                    return await stream.read()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NoSuchBucket"):
                logger.info("Дамп %s не найден в таргете '%s', пробуем следующий", key, target.name)
                continue
            not_found_everywhere = False
            last_exec_error = e
            logger.warning("Ошибка S3 при скачивании из '%s': %s", target.name, e)
            continue
        except Exception as e:  # noqa: BLE001
            not_found_everywhere = False
            last_exec_error = e
            logger.warning("Ошибка при скачивании из '%s': %s", target.name, e)
            continue

    if not_found_everywhere:
        raise BackupNotFoundError(f"Бэкап не найден: {key}")
    raise BackupExecutionError(f"Ошибка S3 при скачивании дампа: {last_exec_error}")


async def _reset_schema() -> None:
    """
    Полностью очищает БД перед восстановлением: DROP SCHEMA public CASCADE.
    Нужно, чтобы остатки новых миграций (таблицы/колонки, которых нет в старом
    дампе) не конфликтовали с повторным `alembic upgrade head` после restore.

    КРИТИЧНО: сам restore-запрос держит открытую сессию БД (require_admin →
    ACCESS SHARE на users). Эндпоинт закрывает её перед вызовом restore, чтобы
    снять блокировку. lock_timeout — страховка, чтобы не висеть вечно, если
    какое-то другое соединение всё же держит конфликтующую блокировку.
    """
    from sqlalchemy import text

    from app.core.database import engine

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL lock_timeout = '20s'"))
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


async def _safety_backup() -> str | None:
    """
    Лёгкий бэкап текущего состояния перед restore: pg_dump + загрузка в S3.
    Без Telegram и retention (они медленные и тут не нужны). Best-effort.
    """
    try:
        db = _parse_db_url()
        dump_bytes = await _run_pg_dump(db)
        key = _backup_key(datetime.now(timezone.utc))
        await _upload(key, dump_bytes)
        logger.info("Предохранительный бэкап перед restore: %s", key)
        return key
    except Exception:
        logger.exception("Предохранительный бэкап перед restore не удался")
        return None


async def _run_pg_restore(db: dict[str, str], dump_bytes: bytes) -> None:
    """pg_restore custom-дампа в (предварительно очищенную) БД."""
    tmp = tempfile.NamedTemporaryFile(
        prefix="restore_", suffix=".dump", delete=False
    )
    try:
        tmp.write(dump_bytes)
        tmp.flush()
        tmp.close()
        cmd = [
            "pg_restore",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "-h", db["host"],
            "-p", db["port"],
            "-U", db["user"],
            "-d", db["dbname"],
            tmp.name,
        ]
        env = {
            "PGPASSWORD": db["password"],
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        }
        logger.info(
            "Запуск pg_restore в %s@%s/%s", db["user"], db["host"], db["dbname"]
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            msg = (stderr or b"").decode(errors="replace").strip()
            raise BackupExecutionError(f"pg_restore exit={proc.returncode}: {msg}")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


async def _run_alembic_upgrade() -> None:
    """Догоняет схему до актуальной после восстановления старого дампа."""
    proc = await asyncio.create_subprocess_exec(
        "alembic", "upgrade", "head",
        cwd="/app",
        env={**os.environ},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = (stderr or stdout or b"").decode(errors="replace").strip()
        raise BackupExecutionError(f"alembic upgrade exit={proc.returncode}: {msg}")


async def restore_backup(key: str) -> dict:
    """
    Откатывает БД к состоянию указанного бэкапа.

    Шаги: предохранительный бэкап текущего состояния (best-effort) → скачать дамп
    → очистить схему → pg_restore → alembic upgrade head → сбросить пул соединений.
    """
    if not _is_backup_configured():
        raise BackupConfigError(
            "Бэкапы не настроены. Задайте S3_* и BACKUP_S3_BUCKET в .env"
        )

    prefix = _normalized_prefix()
    if not key.startswith(prefix) or ".." in key:
        raise BackupNotFoundError("Недопустимый ключ бэкапа")

    started = datetime.now(timezone.utc)

    # 1. Скачать целевой дамп ПЕРВЫМ — при неверном ключе/ошибке S3 падаем сразу,
    #    не трогая текущую БД.
    dump_bytes = await _download_dump(key)

    # 2. Предохранительный бэкап текущего состояния (best-effort), чтобы случайный
    #    откат можно было отменить.
    safety_key = await _safety_backup()

    # 3. Очистить схему, 4. залить дамп, 5. догнать миграции
    db = _parse_db_url()
    await _reset_schema()
    await _run_pg_restore(db, dump_bytes)
    await _run_alembic_upgrade()

    # 6. Сбросить пул соединений: у старых connection'ов кэш планов/каталога
    #    устарел после пересоздания схемы.
    try:
        from app.core.database import engine

        await engine.dispose()
    except Exception:
        logger.exception("Не удалось сбросить пул соединений после restore")

    finished = datetime.now(timezone.utc)
    return {
        "restored_key": key,
        "size_bytes": len(dump_bytes),
        "safety_backup_key": safety_key,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
    }
