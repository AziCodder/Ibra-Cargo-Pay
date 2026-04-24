"""
API журнала изменений (audit log) — только для администратора.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogListOut, AuditLogOut

router = APIRouter(prefix="/api/audit", tags=["audit"])

ALLOWED_ENTITY_TYPES = {
    "project",
    "payment_request",
    "payment",
    "project_item",
    "project_item_requirement",
    "supplier",
    "user",
    "payment_request_comment",
}


@router.get("", response_model=AuditLogListOut)
async def list_audit_logs(
    entity_type: str | None = Query(None),
    user_id: int | None = Query(None),
    entity_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListOut:
    base_q = select(AuditLog)
    count_q = select(func.count(AuditLog.id))

    if entity_type:
        base_q = base_q.where(AuditLog.entity_type == entity_type)
        count_q = count_q.where(AuditLog.entity_type == entity_type)
    if user_id is not None:
        base_q = base_q.where(AuditLog.user_id == user_id)
        count_q = count_q.where(AuditLog.user_id == user_id)
    if entity_id is not None:
        base_q = base_q.where(AuditLog.entity_id == entity_id)
        count_q = count_q.where(AuditLog.entity_id == entity_id)

    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        base_q.options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    entries = result.scalars().all()

    items = [
        AuditLogOut(
            id=entry.id,
            user_id=entry.user_id,
            user_login=entry.user.login if entry.user else None,
            user_full_name=entry.user.full_name if entry.user else None,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            changes=entry.changes,
            created_at=entry.created_at,
        )
        for entry in entries
    ]

    return AuditLogListOut(
        items=items, total=total, page=page, page_size=page_size
    )
