from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.permissions import ensure_project_access
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.payment_request_item import PaymentRequestItem
from app.models.project import Project
from app.models.project_item import ProjectItem
from app.schemas.project import (
    CurrencySummary,
    ProjectCreate,
    ProjectListOut,
    ProjectOut,
    ProjectSummary,
    ProjectUpdate,
)
from app.services import audit_service, export_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListOut)
async def list_projects(
    status: str | None = None,
    sort_by: Literal["name", "created_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = 1,
    page_size: int = 50,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListOut:
    query = select(Project).options(selectinload(Project.client))

    if status in ("active", "closed"):
        query = query.where(Project.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    sort_col = Project.name if sort_by == "name" else Project.created_at
    order = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(order).offset(offset).limit(page_size)
    )
    projects = result.scalars().all()

    return ProjectListOut(
        items=[ProjectOut.model_validate(p) for p in projects],
        total=total,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = Project(
        name=data.name,
        description=data.description,
        status=data.status,
    )
    db.add(project)
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="project",
        entity_id=project.id,
        after=audit_service.entity_snapshot(project),
    )

    await db.commit()
    await db.refresh(project)

    result = await db.execute(
        select(Project)
        .where(Project.id == project.id)
        .options(selectinload(Project.client))
    )
    return ProjectOut.model_validate(result.scalar_one())


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await ensure_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Project)
        .where(Project.id == project.id)
        .options(selectinload(Project.client))
    )
    return ProjectOut.model_validate(result.scalar_one())


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await ensure_project_access(project_id, current_user, db)
    before = audit_service.entity_snapshot(project)

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.status is not None:
        project.status = data.status

    await db.flush()
    after = audit_service.entity_snapshot(project)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="project",
        entity_id=project.id,
        before=before,
        after=after,
    )

    await db.commit()

    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.client))
    )
    return ProjectOut.model_validate(result.scalar_one())


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_project(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await ensure_project_access(project_id, current_user, db)

    req_count = await db.execute(
        select(func.count()).where(PaymentRequest.project_id == project_id)
    )
    if req_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить проект: у него есть заявки на оплату",
        )

    before = audit_service.entity_snapshot(project)
    project_id_snapshot = project.id
    await db.delete(project)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="project",
        entity_id=project_id_snapshot,
        before=before,
    )

    await db.commit()


@router.get("/{project_id}/summary", response_model=ProjectSummary)
async def get_project_summary(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectSummary:
    await ensure_project_access(project_id, current_user, db)

    items_query = select(
        ProjectItem.currency,
        func.sum(ProjectItem.price * ProjectItem.quantity).label("total"),
        func.sum(
            ProjectItem.price * (ProjectItem.commission / 100) * ProjectItem.quantity
        ).label("commission"),
    ).where(ProjectItem.project_id == project_id).group_by(ProjectItem.currency)

    items_result = await db.execute(items_query)
    items_rows = items_result.all()

    paid_query = select(
        Payment.currency,
        func.sum(Payment.amount).label("paid"),
    ).join(
        PaymentRequest, Payment.payment_request_id == PaymentRequest.id
    ).where(
        PaymentRequest.project_id == project_id,
        Payment.status == "confirmed",
    ).group_by(Payment.currency)

    paid_result = await db.execute(paid_query)
    paid_rows = paid_result.all()
    paid_by_currency: dict[str, Decimal] = {
        row.currency: Decimal(str(row.paid)) for row in paid_rows
    }

    invoiced_query = (
        select(
            PaymentRequest.currency,
            func.coalesce(func.sum(PaymentRequestItem.amount), 0).label("invoiced"),
        )
        .join(PaymentRequestItem, PaymentRequestItem.payment_request_id == PaymentRequest.id)
        .where(PaymentRequest.project_id == project_id)
        .group_by(PaymentRequest.currency)
    )
    invoiced_result = await db.execute(invoiced_query)
    invoiced_by_currency: dict[str, Decimal] = {
        row.currency: Decimal(str(row.invoiced)) for row in invoiced_result.all()
    }

    currencies: list[CurrencySummary] = []
    for row in items_rows:
        currency = row.currency
        total = Decimal(str(row.total)) if row.total else Decimal("0")
        commission_val = Decimal(str(row.commission)) if row.commission else Decimal("0")
        paid = paid_by_currency.get(currency, Decimal("0"))
        invoiced = invoiced_by_currency.get(currency, Decimal("0"))
        remaining = total - paid

        summary = CurrencySummary(
            currency=currency,
            total=total,
            invoiced=invoiced,
            paid=paid,
            remaining=remaining,
            commission=commission_val,
        )
        currencies.append(summary)

    return ProjectSummary(currencies=currencies)


@router.get("/{project_id}/export")
async def export_project_excel(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    from io import BytesIO

    await ensure_project_access(project_id, current_user, db)

    is_admin = current_user.role == "admin"
    file_bytes = await export_service.generate_project_excel(
        db, project_id, is_admin=is_admin
    )

    project = await db.get(Project, project_id)
    filename = f"project_{project.project_number}.xlsx"
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
