import logging
from decimal import Decimal
from io import BytesIO

from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.payment_request import PaymentRequest
from app.models.payment_request_item import PaymentRequestItem
from app.models.project import Project
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


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project


async def _check_access(project: Project, current_user) -> None:
    if current_user.role == "client" and project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому проекту")


def _serialize_item(
    item: ProjectItem, is_admin: bool, invoiced_amount: Decimal = Decimal("0")
):
    if is_admin:
        obj = ProjectItemAdminOut.model_validate(item)
    else:
        obj = ProjectItemClientOut.model_validate(item)
    obj.invoiced_amount = invoiced_amount
    return obj


async def _get_invoiced_map(
    item_ids: list[int], db: AsyncSession
) -> dict[int, Decimal]:
    """Возвращает сумму PaymentRequestItem.amount, сгруппированную по project_item_id."""
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


@router.get("")
async def list_items(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, db)
    await _check_access(project, current_user)

    result = await db.execute(
        select(ProjectItem)
        .where(ProjectItem.project_id == project_id)
        .options(
            selectinload(ProjectItem.supplier),
            selectinload(ProjectItem.requirements),
        )
        .order_by(ProjectItem.created_at.asc())
    )
    items = result.scalars().all()
    is_admin = current_user.role == "admin"
    invoiced_map = await _get_invoiced_map([i.id for i in items], db)
    return [_serialize_item(item, is_admin, invoiced_map.get(item.id, Decimal("0"))) for item in items]


@router.get("/import-template")
async def download_items_template(
    project_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await _get_project_or_404(project_id, db)
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
    await _get_project_or_404(project_id, db)

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаются только файлы .xlsx",
        )

    content = await file.read()
    result = await import_service.parse_items_xlsx(db, project_id, content)

    # Audit только если что-то создано
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
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_or_404(project_id, db)

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
        cost_price=data.cost_price,
        currency=data.currency,
        commission=data.commission,
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
        select(ProjectItem)
        .where(ProjectItem.id == item.id)
        .options(
            selectinload(ProjectItem.supplier),
            selectinload(ProjectItem.requirements),
        )
    )
    return ProjectItemAdminOut.model_validate(result.scalar_one())


@router.get("/{item_id}")
async def get_item(
    project_id: int,
    item_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_or_404(project_id, db)
    await _check_access(project, current_user)

    result = await db.execute(
        select(ProjectItem)
        .where(ProjectItem.id == item_id, ProjectItem.project_id == project_id)
        .options(
            selectinload(ProjectItem.supplier),
            selectinload(ProjectItem.requirements),
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    invoiced_map = await _get_invoiced_map([item.id], db)
    return _serialize_item(item, current_user.role == "admin", invoiced_map.get(item.id, Decimal("0")))


@router.put("/{item_id}")
async def update_item(
    project_id: int,
    item_id: int,
    data: ProjectItemUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_or_404(project_id, db)

    result = await db.execute(
        select(ProjectItem)
        .where(ProjectItem.id == item_id, ProjectItem.project_id == project_id)
        .options(
            selectinload(ProjectItem.supplier),
            selectinload(ProjectItem.requirements),
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")

    before = audit_service.entity_snapshot(item)

    update_dict = data.model_dump(exclude_unset=True)

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
        select(ProjectItem)
        .where(ProjectItem.id == item_id)
        .options(
            selectinload(ProjectItem.supplier),
            selectinload(ProjectItem.requirements),
        )
    )
    return ProjectItemAdminOut.model_validate(result.scalar_one())


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    project_id: int,
    item_id: int,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_project_or_404(project_id, db)

    result = await db.execute(
        select(ProjectItem).where(
            ProjectItem.id == item_id, ProjectItem.project_id == project_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")

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
        "Project item deleted: id=%s, name=%s, project_id=%s, by admin",
        item.id, item.name, project_id,
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
