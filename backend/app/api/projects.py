from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
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


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.client))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project


async def _check_project_access(project: Project, current_user) -> None:
    if current_user.role == "client" and project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому проекту")


@router.get("", response_model=ProjectListOut)
async def list_projects(
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListOut:
    query = select(Project).options(selectinload(Project.client))

    # Клиент видит только свои проекты
    if current_user.role == "client":
        query = query.where(Project.client_id == current_user.id)

    if status in ("active", "closed"):
        query = query.where(Project.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Project.created_at.desc()).offset(offset).limit(page_size)
    )
    projects = result.scalars().all()

    return ProjectListOut(
        items=[ProjectOut.model_validate(p) for p in projects],
        total=total,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    from app.models.user import User

    client = await db.get(User, data.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    if client.role != "client":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Выбранный пользователь не является клиентом",
        )

    project = Project(
        name=data.name,
        description=data.description,
        client_id=data.client_id,
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
    project = await _get_project_or_404(project_id, db)
    await _check_project_access(project, current_user)
    return ProjectOut.model_validate(project)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await _get_project_or_404(project_id, db)
    before = audit_service.entity_snapshot(project)

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.client_id is not None:
        from app.models.user import User
        client = await db.get(User, data.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        if client.role != "client":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Выбранный пользователь не является клиентом",
            )
        project.client_id = data.client_id
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


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

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
    project = await _get_project_or_404(project_id, db)
    await _check_project_access(project, current_user)

    # Суммы по позициям номенклатуры (сгруппированные по валюте)
    # total = price * quantity (без комиссии — именно столько выставляем клиенту)
    # commission = price * commission% * quantity (считается отдельно, раз в 2-3 мес.)
    # profit = (price - cost_price) * quantity
    items_query = select(
        ProjectItem.currency,
        func.sum(ProjectItem.price * ProjectItem.quantity).label("total"),
        func.sum(
            ProjectItem.price * (ProjectItem.commission / 100) * ProjectItem.quantity
        ).label("commission"),
        func.sum(
            (ProjectItem.price - ProjectItem.cost_price) * ProjectItem.quantity
        ).label("profit"),
    ).where(ProjectItem.project_id == project_id).group_by(ProjectItem.currency)

    items_result = await db.execute(items_query)
    items_rows = items_result.all()

    # Оплаченные суммы (только confirmed, сгруппированные по валюте платежа)
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

    currencies: list[CurrencySummary] = []
    for row in items_rows:
        currency = row.currency
        total = Decimal(str(row.total)) if row.total else Decimal("0")
        commission_val = Decimal(str(row.commission)) if row.commission else Decimal("0")
        profit_val = Decimal(str(row.profit)) if row.profit else Decimal("0")
        paid = paid_by_currency.get(currency, Decimal("0"))
        remaining = total - paid

        summary = CurrencySummary(
            currency=currency,
            total=total,
            paid=paid,
            remaining=remaining,
            commission=commission_val,  # видят все
            profit=profit_val if current_user.role == "admin" else None,
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

    project = await _get_project_or_404(project_id, db)
    await _check_project_access(project, current_user)

    is_admin = current_user.role == "admin"
    file_bytes = await export_service.generate_project_excel(
        db, project_id, is_admin=is_admin
    )

    filename = f"project_{project.project_number}.xlsx"
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
