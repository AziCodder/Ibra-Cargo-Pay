import logging
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.permissions import can_edit_payment_request, ensure_project_access
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


async def _load_request_items(req: PaymentRequest, db: AsyncSession) -> list[ProjectItem]:
    items: list[ProjectItem] = []
    for pri in req.items:
        item = pri.project_item
        if item is None:
            item = await db.get(ProjectItem, pri.project_item_id)
        if item:
            items.append(item)
    return items


async def _ensure_can_edit_request(
    req: PaymentRequest, user, db: AsyncSession
) -> None:
    items = await _load_request_items(req, db)
    if not can_edit_payment_request(user, items):
        raise HTTPException(
            status_code=403,
            detail="Нет прав на изменение заявки: не все позиции доступны",
        )


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project


async def _check_access(project: Project, current_user) -> None:
    """Доступ к проекту для любого авторизованного пользователя."""
    return


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


async def _build_request_out(
    req: PaymentRequest, db: AsyncSession, user
) -> PaymentRequestOut:
    remaining = await _compute_remaining(req.id, req.total_amount, db)
    items_for_perm = await _load_request_items(req, db)
    can_edit = can_edit_payment_request(user, items_for_perm)

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
        can_edit=can_edit,
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


def _parse_item_ids(item_ids: str | None) -> list[int]:
    if not item_ids:
        return []
    parsed: list[int] = []
    for part in item_ids.split(","):
        part = part.strip()
        if part.isdigit():
            parsed.append(int(part))
    return parsed


@router.get("")
async def list_payment_requests(
    project_id: int,
    sort_by: Literal["created_at", "total_amount", "item_name"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    status_filter: Literal["all", "paid", "unpaid"] = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    item_ids: str | None = Query(None, description="ID позиций через запятую"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, db)
    await _check_access(project, current_user)

    paid_sq = (
        select(
            Payment.payment_request_id.label("req_id"),
            func.coalesce(func.sum(Payment.amount), 0).label("paid_total"),
        )
        .where(Payment.status == "confirmed")
        .group_by(Payment.payment_request_id)
        .subquery()
    )

    item_name_sq = (
        select(
            PaymentRequestItem.payment_request_id.label("req_id"),
            func.min(ProjectItem.name).label("item_sort_name"),
        )
        .join(ProjectItem, PaymentRequestItem.project_item_id == ProjectItem.id)
        .group_by(PaymentRequestItem.payment_request_id)
        .subquery()
    )

    query = select(PaymentRequest).where(PaymentRequest.project_id == project_id)

    if status_filter != "all":
        query = query.outerjoin(paid_sq, PaymentRequest.id == paid_sq.c.req_id)

    if sort_by == "item_name":
        query = query.outerjoin(item_name_sq, PaymentRequest.id == item_name_sq.c.req_id)

    if date_from is not None:
        query = query.where(func.date(PaymentRequest.created_at) >= date_from)
    if date_to is not None:
        query = query.where(func.date(PaymentRequest.created_at) <= date_to)

    parsed_item_ids = _parse_item_ids(item_ids)
    if parsed_item_ids:
        query = query.where(
            PaymentRequest.id.in_(
                select(PaymentRequestItem.payment_request_id).where(
                    PaymentRequestItem.project_item_id.in_(parsed_item_ids)
                )
            )
        )

    if status_filter == "paid":
        query = query.where(
            PaymentRequest.total_amount <= func.coalesce(paid_sq.c.paid_total, 0)
        )
    elif status_filter == "unpaid":
        query = query.where(
            PaymentRequest.total_amount > func.coalesce(paid_sq.c.paid_total, 0)
        )

    if sort_by == "created_at":
        order_col = PaymentRequest.created_at
    elif sort_by == "total_amount":
        order_col = PaymentRequest.total_amount
    else:
        order_col = item_name_sq.c.item_sort_name

    query = query.order_by(
        desc(order_col) if sort_order == "desc" else asc(order_col)
    )

    result = await db.execute(
        query.options(
            selectinload(PaymentRequest.items).selectinload(PaymentRequestItem.project_item),
            selectinload(PaymentRequest.payments),
        )
    )
    requests = result.scalars().unique().all()

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
        items_for_perm = [
            pri.project_item for pri in req.items if pri.project_item is not None
        ]
        output.append(
            PaymentRequestListOut(
                id=req.id,
                project_id=req.project_id,
                total_amount=req.total_amount,
                currency=req.currency,
                due_date=req.due_date,
                priority=req.priority,
                remaining_amount=remaining,
                paid_amount=paid,
                can_edit=can_edit_payment_request(current_user, items_for_perm),
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
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)
    project = await _get_project_or_404(project_id, db)
    project_name = project.name

    # ── Предварительная валидация позиций ──────────────────────────────────────

    # Загружаем все позиции за один проход
    item_objs: dict[int, ProjectItem] = {}
    for item_in in data.items:
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
        item_objs[item_in.project_item_id] = item_obj

    # Все позиции должны быть одной валюты
    currencies = {obj.currency for obj in item_objs.values()}
    if len(currencies) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Все позиции в заявке должны иметь одинаковую валюту",
        )

    # Сумма по каждой позиции не должна превышать остаток (price×qty − уже выставлено)
    for item_in in data.items:
        item_obj = item_objs[item_in.project_item_id]
        max_amount = item_obj.price * item_obj.quantity

        invoiced_result = await db.execute(
            select(func.coalesce(func.sum(PaymentRequestItem.amount), 0)).where(
                PaymentRequestItem.project_item_id == item_in.project_item_id
            )
        )
        already_invoiced = Decimal(str(invoiced_result.scalar_one()))
        remaining = max_amount - already_invoiced

        if Decimal(str(item_in.amount)) > remaining + Decimal("0.01"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Сумма по позиции «{item_obj.name}» ({item_in.amount}) "
                    f"превышает допустимый остаток ({remaining:.2f})"
                ),
            )

    # Пересчитываем total_amount из позиций (не доверяем клиенту)
    computed_total = sum(Decimal(str(i.amount)) for i in data.items)
    detected_currency = next(iter(currencies))

    # ──────────────────────────────────────────────────────────────────────────

    req = PaymentRequest(
        project_id=project_id,
        total_amount=computed_total,
        currency=detected_currency,
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
        item_obj = item_objs[item_in.project_item_id]
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

    # Уведомляем автора заявки (fire-and-forget)
    creator = await db.get(User, current_user.id)
    notification_service.notify_payment_request_created(
        client_chat_id=creator.telegram_chat_id if creator else None,
        project_name=project_name,
        project_id=project_id,
        req_id=req_id_snapshot,
        total_amount=computed_total,
        currency=detected_currency,
        items_names=", ".join(item_names),
        payment_details=data.payment_details,
        requisites=data.requisites,
    )

    loaded = await _load_request(req_id_snapshot, project_id, db)
    return await _build_request_out(loaded, db, current_user)


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
    return await _build_request_out(req, db, current_user)


@router.put("/{req_id}")
async def update_payment_request(
    project_id: int,
    req_id: int,
    data: PaymentRequestUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)
    req = await _load_request(req_id, project_id, db)
    await _ensure_can_edit_request(req, current_user, db)
    before = audit_service.entity_snapshot(req)

    # ── Обновление позиций и пересчёт суммы ─────────────────────────────────
    if data.items is not None:
        new_total = Decimal("0")
        for item_in in data.items:
            # Находим запись PaymentRequestItem для этой заявки
            pri_result = await db.execute(
                select(PaymentRequestItem).where(
                    PaymentRequestItem.payment_request_id == req_id,
                    PaymentRequestItem.project_item_id == item_in.project_item_id,
                )
            )
            pri = pri_result.scalar_one_or_none()
            if not pri:
                raise HTTPException(
                    status_code=404,
                    detail=f"Позиция {item_in.project_item_id} не найдена в этой заявке",
                )

            # Максимальная сумма по позиции проекта
            item_obj = await db.get(ProjectItem, item_in.project_item_id)
            if not item_obj:
                raise HTTPException(status_code=404, detail="Позиция проекта не найдена")
            max_amount = item_obj.price * item_obj.quantity

            # Уже выставлено по другим заявкам (исключая текущую)
            invoiced_result = await db.execute(
                select(func.coalesce(func.sum(PaymentRequestItem.amount), 0)).where(
                    PaymentRequestItem.project_item_id == item_in.project_item_id,
                    PaymentRequestItem.payment_request_id != req_id,
                )
            )
            already_invoiced = Decimal(str(invoiced_result.scalar_one()))
            available = max_amount - already_invoiced

            if Decimal(str(item_in.amount)) > available + Decimal("0.01"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Сумма по позиции «{item_obj.name}» ({item_in.amount}) "
                        f"превышает допустимый остаток ({available:.2f})"
                    ),
                )

            pri.amount = item_in.amount
            new_total += Decimal(str(item_in.amount))

        req.total_amount = new_total

    # ── Обновление остальных полей ────────────────────────────────────────────
    update_fields = data.model_dump(exclude_unset=True, exclude={"items"})
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
    return await _build_request_out(loaded, db, current_user)


@router.delete("/{req_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_request(
    project_id: int,
    req_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ensure_project_access(project_id, current_user, db)

    req = await _load_request(req_id, project_id, db)
    await _ensure_can_edit_request(req, current_user, db)

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
