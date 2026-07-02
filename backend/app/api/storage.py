"""
API репликации файлового хранилища (dual-write S3).

POST /api/storage/reconcile   — проиграть outbox отставших таргетов (требует X-Backup-Secret).
GET  /api/storage/status      — статус таргетов и размер очереди outbox (admin only).
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.storage_replication_pending import StorageReplicationPending
from app.services import storage_reconcile, storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.post("/reconcile")
async def reconcile_storage(
    x_backup_secret: str = Header(..., alias="X-Backup-Secret"),
):
    """Догоняет отставшие S3-таргеты по outbox. Авторизация тем же секретом, что и бэкапы."""
    if x_backup_secret != settings.backup_trigger_secret:
        raise HTTPException(status_code=403, detail="Неверный секрет")
    return await storage_reconcile.reconcile_once()


@router.get("/status")
async def storage_status(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Список настроенных таргетов и число незавершённых операций репликации."""
    pending = (
        await db.execute(select(func.count()).select_from(StorageReplicationPending))
    ).scalar_one()
    targets = [
        {"name": t.name, "endpoint": t.endpoint_url, "bucket": t.bucket}
        for t in storage_service.file_targets()
    ]
    return {
        "targets": targets,
        "dual_write": len(targets) >= 2,
        "pending_replications": int(pending),
    }
