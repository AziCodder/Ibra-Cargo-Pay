"""
API резервных копий БД.

POST /api/backups/run        — запуск из sidecar/cron (требует X-Backup-Secret).
POST /api/backups/run-admin  — ручной запуск из UI (требует JWT администратора).
GET  /api/backups            — список бэкапов (admin only).
GET  /api/backups/download-url?key=... — presigned URL (admin only).
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.dependencies import require_admin
from app.services import backup_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backups", tags=["backups"])


class RestoreRequest(BaseModel):
    key: str = Field(..., min_length=1)


@router.post("/run")
async def run_backup_from_cron(
    x_backup_secret: str = Header(..., alias="X-Backup-Secret"),
):
    """Точка входа для sidecar-контейнера с cron. Авторизация по секрету."""
    if x_backup_secret != settings.backup_trigger_secret:
        raise HTTPException(status_code=403, detail="Неверный секрет бэкапа")
    try:
        return await backup_service.run_backup()
    except backup_service.BackupConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except backup_service.BackupExecutionError as e:
        logger.error("Cron-бэкап провален: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-admin")
async def run_backup_admin(_admin=Depends(require_admin)):
    """Ручной запуск бэкапа из админ-UI."""
    try:
        return await backup_service.run_backup()
    except backup_service.BackupConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except backup_service.BackupExecutionError as e:
        logger.error("Ручной бэкап провален: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore-admin")
async def restore_backup_admin(
    payload: RestoreRequest,
    _admin=Depends(require_admin),
):
    """Откат БД к состоянию указанного бэкапа. Только admin. ОПАСНО: перезатирает данные."""
    try:
        return await backup_service.restore_backup(payload.key)
    except backup_service.BackupConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except backup_service.BackupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except backup_service.BackupExecutionError as e:
        logger.error("Восстановление из бэкапа провалено: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_backups_endpoint(
    limit: int = Query(50, ge=1, le=500),
    _admin=Depends(require_admin),
):
    if not backup_service._is_backup_configured():
        return {"configured": False, "items": []}
    items = await backup_service.list_backups(limit=limit)
    return {
        "configured": True,
        "bucket": settings.backup_s3_bucket,
        "retention_days": settings.backup_retention_days,
        "items": items,
    }


@router.get("/download-url")
async def get_backup_download_url(
    key: str = Query(..., min_length=1),
    _admin=Depends(require_admin),
):
    if not settings.backup_s3_bucket:
        raise HTTPException(status_code=503, detail="Бэкапы не настроены")
    prefix = settings.backup_s3_prefix
    if not prefix.endswith("/"):
        prefix += "/"
    if not key.startswith(prefix):
        raise HTTPException(status_code=400, detail="Недопустимый ключ")

    import aioboto3
    from botocore.config import Config as BotocoreConfig

    creds = backup_service._backup_creds()
    session = aioboto3.Session(
        aws_access_key_id=creds["access_key_id"],
        aws_secret_access_key=creds["secret_access_key"],
        region_name=creds["region"],
    )
    cfg = BotocoreConfig(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        connect_timeout=5,
        read_timeout=10,
        retries={"max_attempts": 1},
    )
    async with session.client(
        "s3", endpoint_url=creds["endpoint_url"], config=cfg
    ) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.backup_s3_bucket, "Key": key},
            ExpiresIn=3600,
        )
    return {"url": url}
