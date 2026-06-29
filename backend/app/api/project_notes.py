from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.permissions import ensure_project_access
from app.models.project_note import ProjectNote
from app.schemas.project_note import ProjectNoteCreate, ProjectNoteOut, ProjectNoteUpdate
from app.services import audit_service

router = APIRouter(prefix="/api/projects/{project_id}/notes", tags=["project-notes"])


def _can_view_note(note: ProjectNote, user) -> bool:
    # Общие заметки видят все; личную — только автор (даже админ не видит чужую).
    if note.visibility == "shared":
        return True
    return note.created_by == user.id


def _can_edit_note(note: ProjectNote, user) -> bool:
    # Редактировать заметку может только её автор.
    return note.created_by == user.id


def _can_delete_note(note: ProjectNote, user) -> bool:
    # Удалять может автор или администратор.
    return user.role == "admin" or note.created_by == user.id


def _note_out(note: ProjectNote, user) -> ProjectNoteOut:
    return ProjectNoteOut(
        id=note.id,
        project_id=note.project_id,
        content=note.content,
        visibility=note.visibility,
        created_by=note.created_by,
        author_name=note.author.full_name if note.author else "—",
        created_at=note.created_at,
        updated_at=note.updated_at,
        can_edit=_can_edit_note(note, user),
        can_delete=_can_delete_note(note, user),
    )


async def _get_note_or_404(
    project_id: int, note_id: int, db: AsyncSession
) -> ProjectNote:
    result = await db.execute(
        select(ProjectNote)
        .where(ProjectNote.id == note_id, ProjectNote.project_id == project_id)
        .options(selectinload(ProjectNote.author))
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    return note


@router.get("", response_model=list[ProjectNoteOut])
async def list_notes(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectNoteOut]:
    await ensure_project_access(project_id, current_user, db)

    query = (
        select(ProjectNote)
        .where(ProjectNote.project_id == project_id)
        .options(selectinload(ProjectNote.author))
        .order_by(ProjectNote.created_at.desc())
    )

    # Личные заметки видны только автору (включая админа — чужие личные скрыты).
    query = query.where(
        or_(
            ProjectNote.visibility == "shared",
            ProjectNote.created_by == current_user.id,
        )
    )

    result = await db.execute(query)
    notes = result.scalars().all()
    return [_note_out(n, current_user) for n in notes if _can_view_note(n, current_user)]


@router.post("", response_model=ProjectNoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(
    project_id: int,
    data: ProjectNoteCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectNoteOut:
    await ensure_project_access(project_id, current_user, db)

    # Клиент не выбирает видимость — все его заметки общие.
    visibility = data.visibility if current_user.role == "admin" else "shared"
    note = ProjectNote(
        project_id=project_id,
        content=data.content.strip(),
        visibility=visibility,
        created_by=current_user.id,
    )
    db.add(note)
    await db.flush()

    after = audit_service.entity_snapshot(note)
    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="project_note",
        entity_id=note.id,
        after=after,
    )

    await db.commit()
    note = await _get_note_or_404(project_id, note.id, db)
    return _note_out(note, current_user)


@router.put("/{note_id}", response_model=ProjectNoteOut)
async def update_note(
    project_id: int,
    note_id: int,
    data: ProjectNoteUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectNoteOut:
    await ensure_project_access(project_id, current_user, db)
    note = await _get_note_or_404(project_id, note_id, db)

    if not _can_edit_note(note, current_user):
        raise HTTPException(status_code=403, detail="Нет прав на изменение заметки")

    before = audit_service.entity_snapshot(note)
    if data.content is not None:
        note.content = data.content.strip()
    # Менять видимость может только админ; у клиента заметки всегда общие.
    if data.visibility is not None and current_user.role == "admin":
        note.visibility = data.visibility

    await db.flush()
    after = audit_service.entity_snapshot(note)
    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="project_note",
        entity_id=note.id,
        before=before,
        after=after,
    )

    await db.commit()
    await db.refresh(note)
    note = await _get_note_or_404(project_id, note_id, db)
    return _note_out(note, current_user)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_note(
    project_id: int,
    note_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db)
    note = await _get_note_or_404(project_id, note_id, db)

    if not _can_delete_note(note, current_user):
        raise HTTPException(status_code=403, detail="Нет прав на удаление заметки")

    before = audit_service.entity_snapshot(note)
    note_id_snapshot = note.id
    await db.delete(note)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="project_note",
        entity_id=note_id_snapshot,
        before=before,
    )

    await db.commit()
