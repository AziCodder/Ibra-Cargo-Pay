from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.permissions import can_edit_item, ensure_project_access
from app.models.project_item import ProjectItem
from app.models.project_item_requirement import ProjectItemRequirement
from app.schemas.project_item import RequirementCreate, RequirementOut
from app.services import audit_service

router = APIRouter(
    prefix="/api/projects/{project_id}/items/{item_id}/requirements",
    tags=["requirements"],
)

MAX_REQUIREMENTS = 5


async def _get_item_or_404(
    project_id: int, item_id: int, user, db: AsyncSession
) -> ProjectItem:
    await ensure_project_access(project_id, user, db)
    result = await db.execute(
        select(ProjectItem).where(
            ProjectItem.id == item_id, ProjectItem.project_id == project_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    return item


@router.get("", response_model=list[RequirementOut])
async def list_requirements(
    project_id: int,
    item_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RequirementOut]:
    await _get_item_or_404(project_id, item_id, current_user, db)

    result = await db.execute(
        select(ProjectItemRequirement)
        .where(ProjectItemRequirement.item_id == item_id)
        .order_by(ProjectItemRequirement.created_at.asc())
    )
    reqs = result.scalars().all()
    return [RequirementOut.model_validate(r) for r in reqs]


@router.post("", response_model=RequirementOut, status_code=status.HTTP_201_CREATED)
async def add_requirement(
    project_id: int,
    item_id: int,
    data: RequirementCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequirementOut:
    item = await _get_item_or_404(project_id, item_id, current_user, db)

    if not can_edit_item(current_user, item):
        raise HTTPException(
            status_code=403, detail="Нет прав на добавление требований к позиции"
        )

    count_result = await db.execute(
        select(func.count()).where(ProjectItemRequirement.item_id == item_id)
    )
    if count_result.scalar_one() >= MAX_REQUIREMENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Максимум {MAX_REQUIREMENTS} требований для одной позиции",
        )

    req = ProjectItemRequirement(item_id=item_id, text=data.text)
    db.add(req)
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="project_item_requirement",
        entity_id=req.id,
        after=audit_service.entity_snapshot(req),
    )

    await db.commit()
    await db.refresh(req)
    return RequirementOut.model_validate(req)


@router.delete("/{req_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement(
    project_id: int,
    item_id: int,
    req_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    item = await _get_item_or_404(project_id, item_id, current_user, db)

    if not can_edit_item(current_user, item):
        raise HTTPException(
            status_code=403, detail="Нет прав на удаление требований позиции"
        )

    result = await db.execute(
        select(ProjectItemRequirement).where(
            ProjectItemRequirement.id == req_id,
            ProjectItemRequirement.item_id == item_id,
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Требование не найдено")

    before = audit_service.entity_snapshot(req)
    req_id_snapshot = req.id
    await db.delete(req)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="project_item_requirement",
        entity_id=req_id_snapshot,
        before=before,
    )

    await db.commit()
