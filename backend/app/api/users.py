from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.security import get_password_hash
from app.models.project import Project
from app.models.user import User
from app.schemas.user import UserCreate, UserListOut, UserOut, UserUpdate
from app.services import audit_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UserListOut)
async def list_users(
    page: int = 1,
    page_size: int = 50,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListOut:
    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(User))
    total = total_result.scalar_one()

    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    users = result.scalars().all()
    return UserListOut(items=[UserOut.model_validate(u) for u in users], total=total)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    # Проверка уникальности логина
    existing = await db.execute(select(User).where(User.login == data.login))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким логином уже существует",
        )

    user = User(
        full_name=data.full_name,
        login=data.login,
        password_hash=get_password_hash(data.password),
        role=data.role,
        description=data.description,
    )
    db.add(user)
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="user",
        entity_id=user.id,
        after=audit_service.entity_snapshot(user),
    )

    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    before = audit_service.entity_snapshot(user)

    if data.login is not None and data.login != user.login:
        existing = await db.execute(select(User).where(User.login == data.login))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким логином уже существует",
            )
        user.login = data.login

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.password is not None:
        user.password_hash = get_password_hash(data.password)
    if data.role is not None:
        user.role = data.role
    if data.description is not None:
        user.description = data.description
    if data.telegram_chat_id is not None:
        user.telegram_chat_id = data.telegram_chat_id

    await db.flush()
    after = audit_service.entity_snapshot(user)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=after,
    )

    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка: нельзя удалить пользователя, у которого есть проекты
    project_count = await db.execute(
        select(func.count()).where(Project.client_id == user_id)
    )
    if project_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить пользователя: у него есть привязанные проекты",
        )

    before = audit_service.entity_snapshot(user)
    user_id_snapshot = user.id

    await db.delete(user)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="user",
        entity_id=user_id_snapshot,
        before=before,
    )

    await db.commit()


@router.post("/{user_id}/telegram-link", response_model=dict)
async def generate_telegram_link(
    user_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Сгенерировать одноразовый токен для привязки Telegram аккаунта."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    token = jwt.encode(
        {"sub": str(user_id), "type": "tg_link", "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return {"token": token}
