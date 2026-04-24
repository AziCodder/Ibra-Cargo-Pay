"""
Сервис журнала изменений (audit log).

Пишет в таблицу audit_log факты create / update / delete для основных сущностей
системы (projects, payment_requests, payments, project_items, suppliers, users)
с diff-ом изменённых полей в виде JSONB.

Не коммитит транзакцию — коммит делает вызывающая ручка.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# Поля, которые исключаются из snapshot (файлы, хэши и т.п.)
EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {"password_hash", "file_path", "file_name", "document_1", "document_2", "document_3"}
)


def _jsonable(value: Any) -> Any:
    """Приводит значение к JSON-совместимому виду."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    # Для остальных типов — строковое представление
    return str(value)


def entity_snapshot(obj: Any) -> dict[str, Any]:
    """
    Делает JSON-совместимый снимок полей ORM-объекта.

    Берёт все столбцы из __table__.columns, исключая EXCLUDED_FIELDS.
    Использует sqlalchemy.inspect чтобы не триггерить lazy-load expired атрибутов
    (после flush() некоторые поля с server_default/onupdate могут быть expired и
    обращение к ним в async-контексте вызывает MissingGreenlet).
    """
    if obj is None:
        return {}

    try:
        columns = obj.__table__.columns
    except AttributeError:
        return {}

    # Получаем "сырое" состояние атрибутов без триггера lazy-load
    try:
        state = sa_inspect(obj)
        committed: dict[str, Any] = dict(obj.__dict__)
        unloaded: set[str] = set(state.unloaded)
    except Exception:  # noqa: BLE001
        committed = {}
        unloaded = set()

    snapshot: dict[str, Any] = {}
    for col in columns:
        name = col.name
        if name in EXCLUDED_FIELDS:
            continue
        # Если атрибут в __dict__ — берём напрямую (без IO).
        # Если expired/unloaded — пропускаем (в snapshot не попадёт)
        if name in committed:
            snapshot[name] = _jsonable(committed[name])
        elif name not in unloaded:
            # Значение может быть в committed_state через attribute_state
            try:
                snapshot[name] = _jsonable(getattr(obj, name, None))
            except Exception:  # noqa: BLE001
                continue
    return snapshot


def diff_dict(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any]:
    """Вычисляет JSON-diff между snapshot'ами.

    - create (before=None): возвращает {"after": after}
    - delete (after=None): возвращает {"before": before}
    - update: возвращает {"field": {"old": ..., "new": ...}} только для изменённых
    """
    if before is None and after is not None:
        return {"after": after}
    if after is None and before is not None:
        return {"before": before}
    if before is None or after is None:
        return {}

    changes: dict[str, Any] = {}
    keys = set(before.keys()) | set(after.keys())
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changes[key] = {"old": old, "new": new}
    return changes


async def log_action(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """
    Записывает событие в audit_log.

    Вызов НЕ коммитит транзакцию — ожидается общий commit из ручки.
    Любые ошибки логируются, но не пробрасываются (fail-soft).
    """
    if action not in ("created", "updated", "deleted"):
        logger.error("audit_service: invalid action %r", action)
        return

    try:
        changes = diff_dict(before, after)
        if action == "updated" and not changes:
            # Нет фактических изменений — пропускаем
            return

        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes or None,
        )
        db.add(entry)
    except Exception as exc:  # noqa: BLE001
        logger.exception("audit_service.log_action failed: %s", exc)
