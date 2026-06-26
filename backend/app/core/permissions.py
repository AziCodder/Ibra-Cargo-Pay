"""Централизованные проверки прав доступа (чек-лист Ibra Cargo Pay)."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, Sequence

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Файлы с дублирующими _check_* — заменить на helpers из этого модуля по мере разделов:
REFACTOR_ACCESS_CHECKLIST: tuple[str, ...] = (
    "backend/app/api/projects.py",  # _check_project_access → ensure_project_access
    "backend/app/api/project_items.py",  # _check_access
    "backend/app/api/project_item_requirements.py",  # _check_access
    "backend/app/api/payment_requests.py",  # _check_access
    "backend/app/api/payment_request_comments.py",  # _load_request_and_check_access
    "backend/app/api/payments.py",  # inline client_id checks
    "backend/app/api/files.py",  # inline client_id checks
)


class UserLike(Protocol):
    id: int
    role: str


class ItemLike(Protocol):
    shared_access: bool
    price: Decimal


class PaymentLike(Protocol):
    created_by: int


def can_access_project(user: UserLike) -> bool:
    """Любой авторизованный пользователь имеет доступ к проекту."""
    return user is not None


def can_edit_project(user: UserLike) -> bool:
    return user.role in ("admin", "client")


def can_edit_item(user: UserLike, item: ItemLike) -> bool:
    if user.role == "admin":
        return True
    return user.role == "client" and item.shared_access


def can_view_item_cost(user: UserLike) -> bool:
    return user.role == "admin"


def all_items_accessible(user: UserLike, items: Sequence[ItemLike]) -> bool:
    if user.role == "admin":
        return True
    return bool(items) and all(item.shared_access for item in items)


def can_edit_payment_request(user: UserLike, items: Sequence[ItemLike]) -> bool:
    return all_items_accessible(user, items)


def can_delete_payment(
    user: UserLike, payment: PaymentLike, items: Sequence[ItemLike]
) -> bool:
    if user.role == "admin":
        return True
    return payment.created_by == user.id and all_items_accessible(user, items)


def default_shared_access_for_creator(role: str) -> bool:
    return role == "client"


def effective_cost_price(item: ItemLike) -> Decimal:
    cost = getattr(item, "cost_price", None)
    if cost is None:
        return item.price
    return cost


async def ensure_project_access(
    project_id: int,
    user: UserLike,
    db: AsyncSession,
):
    """Загрузить проект или 404; доступ для любой роли (can_access_project)."""
    from app.models.project import Project

    if not can_access_project(user):
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project
