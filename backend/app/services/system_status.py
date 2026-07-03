"""
Агрегатор статуса инфраструктуры для админ-панели ("Состояние системы").

Проверяет вживую: backend (себя), БД (роль + доступность), потоковую репликацию
PostgreSQL, S3-таргеты файлов (primary/secondary), S3-таргеты бэкапов, очередь
догоняющей синхронизации (outbox) и доступность второго сервера по WireGuard.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

Status = Literal["ok", "degraded", "down", "not_configured"]


@dataclass
class ComponentStatus:
    key: str
    label: str
    status: Status
    detail: str = ""
    latency_ms: int | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }
        if self.latency_ms is not None:
            d["latency_ms"] = self.latency_ms
        return d


async def _check_database(db: AsyncSession) -> ComponentStatus:
    start = time.monotonic()
    try:
        recovery = (await db.execute(text("SELECT pg_is_in_recovery()"))).scalar_one()
        latency_ms = int((time.monotonic() - start) * 1000)
        role = "standby (реплика, read-only)" if recovery else "primary (принимает записи)"
        return ComponentStatus("database", "База данных", "ok", f"Роль: {role}", latency_ms)
    except Exception as e:  # noqa: BLE001
        return ComponentStatus("database", "База данных", "down", str(e)[:200])


async def _check_replication(db: AsyncSession, node_role: str) -> ComponentStatus:
    try:
        if node_role == "primary":
            rows = (
                await db.execute(
                    text(
                        "SELECT client_addr, state, "
                        "pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes "
                        "FROM pg_stat_replication"
                    )
                )
            ).all()
            if not rows:
                return ComponentStatus(
                    "replication",
                    "Репликация БД",
                    "degraded",
                    "Нет подключённых реплик — резервный сервер не синхронизируется",
                )
            parts = [f"{r.client_addr} ({r.state}, лаг {r.lag_bytes} байт)" for r in rows]
            return ComponentStatus("replication", "Репликация БД", "ok", "; ".join(parts))
        else:
            row = (
                await db.execute(
                    text(
                        "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))"
                        "::int AS age_sec"
                    )
                )
            ).one()
            age = row.age_sec
            if age is None:
                return ComponentStatus(
                    "replication", "Репликация БД", "degraded", "Нет данных о последней репликации"
                )
            status: Status = "ok" if age < 300 else "degraded"
            return ComponentStatus("replication", "Репликация БД", status, f"Отставание: {age} сек")
    except Exception as e:  # noqa: BLE001
        return ComponentStatus("replication", "Репликация БД", "down", str(e)[:200])


async def _check_s3_target(key: str, label: str, target) -> ComponentStatus:
    from app.services import storage_service

    if target is None:
        return ComponentStatus(key, label, "not_configured", "Не настроен")

    start = time.monotonic()
    try:
        async with storage_service.client(target, read_timeout=8) as s3:
            await s3.head_bucket(Bucket=target.bucket)
        latency_ms = int((time.monotonic() - start) * 1000)
        return ComponentStatus(key, label, "ok", f"{target.endpoint_url} / {target.bucket}", latency_ms)
    except Exception as e:  # noqa: BLE001
        return ComponentStatus(key, label, "down", str(e)[:200])


async def _check_backup_targets() -> list[ComponentStatus]:
    from app.services import backup_service

    targets = backup_service._backup_targets()
    if not targets:
        return [ComponentStatus("backup", "Бэкапы БД", "not_configured", "Не настроены")]
    return [
        await _check_s3_target(f"backup_{t.name}", f"Бэкапы: {t.name}", t) for t in targets
    ]


async def _check_storage_outbox(db: AsyncSession) -> ComponentStatus:
    from app.models.storage_replication_pending import StorageReplicationPending

    pending = (
        await db.execute(select(func.count()).select_from(StorageReplicationPending))
    ).scalar_one()
    if pending == 0:
        return ComponentStatus(
            "storage_outbox", "Очередь синхронизации файлов", "ok", "Всё синхронизировано"
        )
    return ComponentStatus(
        "storage_outbox", "Очередь синхронизации файлов", "degraded", f"В очереди: {pending}"
    )


def _self_vps_status(node_role: str) -> ComponentStatus:
    label = "VPS основной" if node_role == "primary" else "VPS резервный"
    return ComponentStatus("vps_self", label, "ok", "Этот сервер (вы сейчас на нём)")


async def _check_peer_vps(node_role: str) -> ComponentStatus:
    import httpx

    if node_role == "primary":
        peer_ip = settings.standby_wg_ip
        label = "VPS резервный"
    else:
        peer_ip = settings.primary_wg_ip
        label = "VPS основной"

    if not peer_ip:
        return ComponentStatus("vps_peer", label, "not_configured", "WireGuard IP не задан")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3) as http_client:
            resp = await http_client.get(f"http://{peer_ip}:8000/health")
        latency_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            return ComponentStatus("vps_peer", label, "ok", f"{peer_ip}:8000 отвечает", latency_ms)
        return ComponentStatus("vps_peer", label, "degraded", f"HTTP {resp.status_code}", latency_ms)
    except Exception as e:  # noqa: BLE001
        return ComponentStatus("vps_peer", label, "down", f"Недоступен по {peer_ip}: {str(e)[:150]}")


def _overall(components: list[ComponentStatus]) -> Status:
    overall: Status = "ok"
    for c in components:
        if c.status == "down":
            return "down"
        if c.status == "degraded":
            overall = "degraded"
    return overall


async def get_system_status(db: AsyncSession) -> dict:
    """Собирает статус всех компонентов инфраструктуры. Используется /api/system/status."""
    from app.services import storage_service

    node_role = settings.node_role

    components: list[ComponentStatus] = [
        ComponentStatus("backend", "Backend (API)", "ok", f"Роль узла: {node_role}"),
        await _check_database(db),
    ]

    file_targets = storage_service.file_targets()
    components.append(
        await _check_s3_target(
            "s3_primary", "S3 основной (файлы)", storage_service.target_by_name("primary", file_targets)
        )
    )
    components.append(
        await _check_s3_target(
            "s3_secondary",
            "S3 резервный (файлы)",
            storage_service.target_by_name("secondary", file_targets),
        )
    )
    components.extend(await _check_backup_targets())
    components.append(await _check_replication(db, node_role))
    components.append(await _check_storage_outbox(db))
    components.append(_self_vps_status(node_role))
    components.append(await _check_peer_vps(node_role))

    return {
        "node_role": node_role,
        "overall_status": _overall(components),
        "components": [c.to_dict() for c in components],
    }
