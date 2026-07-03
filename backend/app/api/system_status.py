"""
API статуса инфраструктуры ("Состояние системы" в админ-панели).

GET /api/system/status — агрегированный статус backend/БД/S3/репликации/VPS (admin only).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.services.system_status import get_system_status

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status_endpoint(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await get_system_status(db)
