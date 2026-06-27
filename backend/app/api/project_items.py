import logging
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.permissions import (
    can_edit_item,
    default_shared_access_for_creator,
    ensure_project_access,
)
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.payment_request_item import PaymentRequestItem
from app.models.project_item import ProjectItem
from app.models.supplier import Supplier
from app.schemas.project_item import (
    ProjectItemAdminOut,
    ProjectItemClientOut,
    ProjectItemCreate,
    ProjectItemUpdate,
)
from app.services import audit_service, import_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/items", tags=["project-items"])

_ITEM_LOAD = (
    selectinload(ProjectItem.supplier),
    selectinload(ProjectItem.requirements),
)


async def _get_item_or_404(
    project_id: int, item_id: int, db: AsyncSession
) -> ProjectItem:
    result = await db.execute(
        select(ProjectItem)
        .where(ProjectItem.id == item_id, ProjectItem.project_id == project_id)
        .options(*_ITEM_LOAD)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    return item


async def _next_sort_order(project_id: int, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(ProjectItem.sort_order), -1)).where(
            ProjectItem.project_id == project_id
        )
    )
    return int(result.scalar_one()) + 1


def _resolve_cost_price_on_create(user, data: ProjectItemCreate) -> Decimal | None:
    if user.role == "client":
        return data.price
    return data.cost_price


def _serialize_item(
    item: ProjectItem,
    user,
    invoiced_amount: Decimal = Decimal("0"),
    paid_amount: Decimal = Decimal("0"),
):
    is_admin = user.role == "admin"
    if is_admin:
        obj = ProjectItemAdminOut.model_validate(item)
    else:
        obj = ProjectItemClientOut.model_validate(item)
    obj.can_edit = can_edit_item(user, item)
    obj.invoiced_amount = invoiced_amount
    obj.paid_amount = paid_amount
    return obj


async def _get_invoiced_map(
    item_ids: list[int], db: AsyncSession
) -> dict[int, Decimal]:
    if not item_ids:
        return {}
    result = await db.execute(
        select(
            PaymentRequestItem.project_item_id,
            func.coalesce(func.sum(PaymentRequestItem.amount), 0).label("invoiced"),
        )
        .where(PaymentRequestItem.project_item_id.in_(item_ids))
        .group_by(PaymentRequestItem.project_item_id)
    )
    return {row[0]: Decimal(str(row[1])) for row in result.all()}


async def _get_paid_map(
    item_ids: list[int], db: AsyncSession
) -> dict[int, Decimal]:
    if not item_ids:
        return {}

    confirmed_sq = (
        select(
            Payment.payment_request_id,
            func.coalesce(func.sum(Payment.amount), 0).label("confirmed_total"),
        )
        .where(Payment.status == "confirmed")
        .group_by(Payment.payment_request_id)
        .subquery()
    )

    result = await db.execute(
        select(
            PaymentRequestItem.project_item_id,
            func.coalesce(
                func.sum(
                    PaymentRequestItem.amount
                    / PaymentRequest.total_amount
                    * func.coalesce(confirmed_sq.c.confirmed_total, 0)
                ),
                0,
            ).label("paid"),
        )
        .join(PaymentRequest, PaymentRequestItem.payment_request_id == PaymentRequest.id)
        .outerjoin(confirmed_sq, confirmed_sq.c.payment_request_id == PaymentRequest.id)
        .where(PaymentRequestItem.project_item_id.in_(item_ids))
        .group_by(PaymentRequestItem.project_item_id)
    )
    return {row[0]: Decimal(str(row[1])) for row in result.all()}


@router.get("")
async def list_items(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)

    result = await db.execute(
        select(ProjectItem)
        .where(ProjectItem.project_id == project_id)
        .options(*_ITEM_LOAD)
        .order_by(ProjectItem.sort_order.asc(), ProjectItem.id.asc())
    )
    items = result.scalars().all()
    item_ids = [i.id for i in items]
    invoiced_map = await _get_invoiced_map(item_ids, db)
    paid_map = await _get_paid_map(item_ids, db)
    return [
        _serialize_item(
            item,
            current_user,
            invoiced_map.get(item.id, Decimal("0")),
            paid_map.get(item.id, Decimal("0")),
        )
        for item in items
    ]


@router.get("/import-template")
async def download_items_template(
    project_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await ensure_project_access(project_id, _admin, db)
    file_bytes = import_service.generate_items_template()
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": "attachment; filename=items_template.xlsx"
        },
    )


@router.post("/import")
async def import_items(
    project_id: int,
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаются только файлы .xlsx",
        )

    content = await file.read()
    result = await import_service.parse_items_xlsx(
        db, project_id, content, created_by=current_user.id
    )

    if result.get("created", 0) > 0:
        await audit_service.log_action(
            db,
            user_id=current_user.id,
            action="created",
            entity_type="project_item",
            entity_id=project_id,
            after={"imported_count": result["created"], "project_id": project_id},
        )
        await db.commit()

    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_item(
    project_id: int,
    data: ProjectItemCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)

    if data.supplier_id is not None:
        supplier = await db.get(Supplier, data.supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Поставщик с id={data.supplier_id} не найден",
            )

    item = ProjectItem(
        project_id=project_id,
        name=data.name,
        details=data.details,
        quantity=data.quantity,
        supplier_id=data.supplier_id,
        price=data.price,
        cost_price=_resolve_cost_price_on_create(current_user, data),
        currency=data.currency,
        commission=data.commission,
        created_by=current_user.id,
        shared_access=default_shared_access_for_creator(current_user.role),
        sort_order=await _next_sort_order(project_id, db),
    )
    db.add(item)
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="project_item",
        entity_id=item.id,
        after=audit_service.entity_snapshot(item),
    )

    await db.commit()
    await db.refresh(item)

    result = await db.execute(
        select(ProjectItem).where(ProjectItem.id == item.id).options(*_ITEM_LOAD)
    )
    loaded = result.scalar_one()
    return _serialize_item(loaded, current_user)


@router.get("/{item_id}")
async def get_item(
    project_id: int,
    item_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)
    item = await _get_item_or_404(project_id, item_id, db)
    invoiced_map = await _get_invoiced_map([item.id], db)
    paid_map = await _get_paid_map([item.id], db)
    return _serialize_item(
        item,
        current_user,
        invoiced_map.get(item.id, Decimal("0")),
        paid_map.get(item.id, Decimal("0")),
    )


@router.put("/{item_id}")
async def update_item(
    project_id: int,
    item_id: int,
    data: ProjectItemUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)
    item = await _get_item_or_404(project_id, item_id, db)

    if not can_edit_item(current_user, item):
        raise HTTPException(status_code=403, detail="Нет прав на редактирование позиции")

    before = audit_service.entity_snapshot(item)
    update_dict = data.model_dump(exclude_unset=True)

    if current_user.role != "admin":
        update_dict.pop("shared_access", None)
        update_dict.pop("cost_price", None)

    for field, value in update_dict.items():
        setattr(item, field, value)

    await db.flush()
    after = audit_service.entity_snapshot(item)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="project_item",
        entity_id=item.id,
        before=before,
        after=after,
    )

    await db.commit()

    result = await db.execute(
        select(ProjectItem).where(ProjectItem.id == item_id).options(*_ITEM_LOAD)
    )
    return _serialize_item(result.scalar_one(), current_user)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_item(
    project_id: int,
    item_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ensure_project_access(project_id, current_user, db)

    result = await db.execute(
        select(ProjectItem).where(
            ProjectItem.id == item_id, ProjectItem.project_id == project_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")

    if not can_edit_item(current_user, item):
        raise HTTPException(status_code=403, detail="Нет прав на удаление позиции")

    pri_count = await db.execute(
        select(func.count()).where(PaymentRequestItem.project_item_id == item_id)
    )
    if pri_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить позицию: она используется в заявках на оплату",
        )

    before = audit_service.entity_snapshot(item)
    item_id_snapshot = item.id

    logger.info(
        "Project item deleted: id=%s, name=%s, project_id=%s, by user=%s",
        item.id,
        item.name,
        project_id,
        current_user.id,
    )
    await db.delete(item)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="project_item",
        entity_id=item_id_snapshot,
        before=before,
    )

    await db.commit()


async def _swap_sort_order(
    item: ProjectItem,
    neighbor: ProjectItem,
    db: AsyncSession,
    user,
) -> None:
    if not can_edit_item(user, item) or not can_edit_item(user, neighbor):
        raise HTTPException(status_code=403, detail="Нет прав на изменение порядка")
    item.sort_order, neighbor.sort_order = neighbor.sort_order, item.sort_order
    await db.flush()


@router.post("/{item_id}/move-up")
async def move_item_up(
    project_id: int,
    item_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)
    item = await _get_item_or_404(project_id, item_id, db)

    neighbor_result = await db.execute(
        select(ProjectItem)
        .where(
            ProjectItem.project_id == project_id,
            ProjectItem.sort_order == item.sort_order - 1,
        )
        .options(*_ITEM_LOAD)
    )
    neighbor = neighbor_result.scalar_one_or_none()
    if not neighbor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Позиция уже первая в списке",
        )

    await _swap_sort_order(item, neighbor, db, current_user)
    await db.commit()
    return _serialize_item(item, current_user)


@router.post("/{item_id}/move-down")
async def move_item_down(
    project_id: int,
    item_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)
    item = await _get_item_or_404(project_id, item_id, db)

    neighbor_result = await db.execute(
        select(ProjectItem)
        .where(
            ProjectItem.project_id == project_id,
            ProjectItem.sort_order == item.sort_order + 1,
        )
        .options(*_ITEM_LOAD)
    )
    neighbor = neighbor_result.scalar_one_or_none()
    if not neighbor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Позиция уже последняя в списке",
        )

    await _swap_sort_order(item, neighbor, db, current_user)
    await db.commit()
    return _serialize_item(item, current_user)
