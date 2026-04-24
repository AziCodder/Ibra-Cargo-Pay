import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.payment_request_item import PaymentRequestItem
from app.models.project import Project
from app.models.project_item import ProjectItem
from app.models.user import User
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestListOut,
    PaymentRequestItemOut,
    PaymentRequestOut,
    PaymentRequestUpdate,
    AttachmentOut,
    PaymentShortOut,
)
from app.services import audit_service, notification_service

router = APIRouter(prefix="/api/projects/{project_id}/payment-requests", tags=["payment-requests"])


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project


async def _check_access(project: Project, current_user) -> None:
    if current_user.role == "client" and project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому проекту")


async def _compute_remaining(req_id: int, total_amount: Decimal, db: AsyncSession) -> Decimal:
    """Остаток рассчитывается ТОЛЬКО по confirmed платежам.
    Pending и rejected в остаток не входят."""
    paid_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.payment_request_id == req_id,
            Payment.status == "confirmed",
        )
    )
    paid = Decimal(str(paid_result.scalar_one()))
    return total_amount - paid


async def _build_request_out(req: PaymentRequest, db: AsyncSession) -> PaymentRequestOut:
    remaining = await _compute_remaining(req.id, req.total_amount, db)

    items_out = []
    for pri in req.items:
        item_name = pri.project_item.name if pri.project_item else f"#{pri.project_item_id}"
        items_out.append(
            PaymentRequestItemOut(
                id=pri.id,
                project_item_id=pri.project_item_id,
                project_item_name=item_name,
                amount=pri.amount,
            )
        )

    attachments_out = [AttachmentOut.model_validate(a) for a in req.attachments]
    payments_out = [PaymentShortOut.model_validate(p) for p in req.payments]

    return PaymentRequestOut(
        id=req.id,
        project_id=req.project_id,
        total_amount=req.total_amount,
        currency=req.currency,
        requisites=req.requisites,
        payment_details=req.payment_details,
        due_date=req.due_date,
        priority=req.priority,
        remaining_amount=remaining,
        items=items_out,
        attachments=attachments_out,
        payments=payments_out,
        created_by=req.created_by,
        created_at=req.created_at,
    )


async def _load_request(req_id: int, project_id: int, db: AsyncSession) -> PaymentRequest:
    result = await db.execute(
        select(PaymentRequest)
        .where(PaymentRequest.id == req_id, PaymentRequest.project_id == project_id)
        .options(
            selectinload(PaymentRequest.items).selectinload(PaymentRequestItem.project_item),
            selectinload(PaymentRequest.attachments),
            selectinload(PaymentRequest.payments),
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Заявка на оплату не найдена")
    return req


@router.get("")
async def list_payment_requests(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, db)
    await _check_access(project, current_user)

    result = await db.execute(
        select(PaymentRequest)
        .where(PaymentRequest.project_id == project_id)
        .options(
            selectinload(PaymentRequest.items).selectinload(PaymentRequestItem.project_item),
            selectinload(PaymentRequest.payments),
        )
        .order_by(PaymentRequest.created_at.desc())
    )
    requests = result.scalars().all()

    # Собираем все remaining_amount одним запросом вместо N+1
    # Учитываем только confirmed платежи (pending/rejected не снижают остаток)
    req_ids = [r.id for r in requests]
    paid_map: dict[int, Decimal] = {}
    if req_ids:
        paid_result = await db.execute(
            select(
                Payment.payment_request_id,
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .where(
                Payment.payment_request_id.in_(req_ids),
                Payment.status == "confirmed",
            )
            .group_by(Payment.payment_request_id)
        )
        paid_map = {row[0]: Decimal(str(row[1])) for row in paid_result.all()}

    output = []
    for req in requests:
        paid = paid_map.get(req.id, Decimal("0"))
        remaining = req.total_amount - paid
        names = ", ".join(
            (pri.project_item.name if pri.project_item else f"#{pri.project_item_id}")
            for pri in req.items
        )
        output.append(
            PaymentRequestListOut(
                id=req.id,
                project_id=req.project_id,
                total_amount=req.total_amount,
                currency=req.currency,
                due_date=req.due_date,
                priority=req.priority,
                remaining_amount=remaining,
                items_names=names,
                created_by=req.created_by,
                created_at=req.created_at,
            )
        )

    return output


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment_request(
    project_id: int,
    data: PaymentRequestCreate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, db)
    # Читаем поля до commit, чтобы они не устарели после flush
    project_name = project.name
    project_client_id = project.client_id

    req = PaymentRequest(
        project_id=project_id,
        total_amount=data.total_amount,
        currency=data.currency,
        requisites=data.requisites,
        payment_details=data.payment_details,
        due_date=data.due_date,
        priority=data.priority,
        created_by=current_user.id,
    )
    db.add(req)
    await db.flush()  # получаем req.id

    item_names: list[str] = []
    for item_in in data.items:
        # Проверяем, что позиция принадлежит проекту
        item_result = await db.execute(
            select(ProjectItem).where(
                ProjectItem.id == item_in.project_item_id,
                ProjectItem.project_id == project_id,
            )
        )
        item_obj = item_result.scalar_one_or_none()
        if not item_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Позиция {item_in.project_item_id} не найдена в этом проекте",
            )
        item_names.append(item_obj.name)
        pri = PaymentRequestItem(
            payment_request_id=req.id,
            project_item_id=item_in.project_item_id,
            amount=item_in.amount,
        )
        db.add(pri)

    req_id_snapshot = req.id

    # Audit log (внутри транзакции)
    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="payment_request",
        entity_id=req_id_snapshot,
        after=audit_service.entity_snapshot(req),
    )

    await db.commit()

    # Уведомляем клиента (fire-and-forget)
    client_user = await db.get(User, project_client_id)
    notification_service.notify_payment_request_created(
        client_chat_id=client_user.telegram_chat_id if client_user else None,
        project_name=project_name,
        project_id=project_id,
        req_id=req_id_snapshot,
        total_amount=data.total_amount,
        currency=data.currency,
        items_names=", ".join(item_names),
    )

    loaded = await _load_request(req_id_snapshot, project_id, db)
    return await _build_request_out(loaded, db)


@router.get("/{req_id}")
async def get_payment_request(
    project_id: int,
    req_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, db)
    await _check_access(project, current_user)

    req = await _load_request(req_id, project_id, db)
    return await _build_request_out(req, db)


@router.put("/{req_id}")
async def update_payment_request(
    project_id: int,
    req_id: int,
    data: PaymentRequestUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_or_404(project_id, db)
    req = await _load_request(req_id, project_id, db)
    before = audit_service.entity_snapshot(req)

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(req, field, value)

    await db.flush()
    after = audit_service.entity_snapshot(req)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="payment_request",
        entity_id=req.id,
        before=before,
        after=after,
    )

    await db.commit()
    loaded = await _load_request(req_id, project_id, db)
    return await _build_request_out(loaded, db)


@router.delete("/{req_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_request(
    project_id: int,
    req_id: int,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_project_or_404(project_id, db)

    result = await db.execute(
        select(PaymentRequest).where(
            PaymentRequest.id == req_id, PaymentRequest.project_id == project_id
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Заявка на оплату не найдена")

    pay_count = await db.execute(
        select(func.count()).where(Payment.payment_request_id == req_id)
    )
    if pay_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить заявку: по ней есть платежи",
        )

    logger.info(
        "Payment request deleted: id=%s, project_id=%s, amount=%s %s, by admin",
        req.id, project_id, req.total_amount, req.currency,
    )
    before = audit_service.entity_snapshot(req)
    req_id_snapshot = req.id
    await db.delete(req)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="payment_request",
        entity_id=req_id_snapshot,
        before=before,
    )

    await db.commit()
