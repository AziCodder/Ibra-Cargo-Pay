"""
API агрегированного дашборда администратора.

Возвращает:
- Кол-во активных / закрытых проектов
- Остатки по всем проектам, сгруппированные по валюте
- 10 последних платежей
- Кол-во полностью оплаченных (closed) заявок
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.project import Project
from app.models.project_item import ProjectItem
from app.schemas.dashboard import (
    CurrencyBalance,
    DashboardSummary,
    RecentPaymentOut,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    # ── Проекты по статусам ──
    active_q = select(func.count(Project.id)).where(Project.status == "active")
    closed_q = select(func.count(Project.id)).where(Project.status == "closed")
    projects_active = (await db.execute(active_q)).scalar_one()
    projects_closed = (await db.execute(closed_q)).scalar_one()

    # ── Итоги по номенклатуре (все проекты) ──
    items_q = select(
        ProjectItem.currency,
        func.sum(
            ProjectItem.price
            * (1 + ProjectItem.commission / 100)
            * ProjectItem.quantity
        ).label("total"),
    ).group_by(ProjectItem.currency)
    items_rows = (await db.execute(items_q)).all()

    # Учитываем только confirmed платежи (pending/rejected не считаются оплатой)
    paid_q = (
        select(
            Payment.currency,
            func.sum(Payment.amount).label("paid"),
        )
        .where(Payment.status == "confirmed")
        .group_by(Payment.currency)
    )
    paid_rows = (await db.execute(paid_q)).all()
    paid_by_currency = {
        row.currency: Decimal(str(row.paid or 0)) for row in paid_rows
    }

    remaining_by_currency: list[CurrencyBalance] = []
    seen_currencies = set()
    for row in items_rows:
        currency = row.currency
        seen_currencies.add(currency)
        total = Decimal(str(row.total or 0))
        paid = paid_by_currency.get(currency, Decimal("0"))
        remaining_by_currency.append(
            CurrencyBalance(
                currency=currency,
                total=total,
                paid=paid,
                remaining=total - paid,
            )
        )
    # Если есть платежи в валюте без позиций — тоже покажем
    for currency, paid in paid_by_currency.items():
        if currency not in seen_currencies:
            remaining_by_currency.append(
                CurrencyBalance(
                    currency=currency,
                    total=Decimal("0"),
                    paid=paid,
                    remaining=-paid,
                )
            )

    remaining_by_currency.sort(key=lambda cb: cb.currency)

    # ── Последние платежи (только confirmed — pending ещё не проведены) ──
    recent_q = (
        select(Payment)
        .where(Payment.status == "confirmed")
        .options(
            selectinload(Payment.creator),
            selectinload(Payment.payment_request).selectinload(PaymentRequest.project),
        )
        .order_by(Payment.created_at.desc())
        .limit(10)
    )
    recent_rows = (await db.execute(recent_q)).scalars().all()
    recent_payments: list[RecentPaymentOut] = []
    for p in recent_rows:
        project = p.payment_request.project if p.payment_request else None
        recent_payments.append(
            RecentPaymentOut(
                id=p.id,
                payment_request_id=p.payment_request_id,
                project_id=project.id if project else 0,
                project_name=project.name if project else "—",
                project_number=project.project_number if project else 0,
                amount=p.amount,
                currency=p.currency,
                note=p.note,
                created_by=p.created_by,
                created_by_full_name=p.creator.full_name if p.creator else "—",
                created_at=p.created_at,
            )
        )

    # ── Закрытые заявки (remaining = 0 по confirmed платежам) ──
    # Заявка считается закрытой, если sum(payments where status='confirmed') >= total_amount
    completed_q = (
        select(func.count(PaymentRequest.id))
        .select_from(PaymentRequest)
        .outerjoin(
            Payment,
            (Payment.payment_request_id == PaymentRequest.id)
            & (Payment.status == "confirmed"),
        )
        .group_by(PaymentRequest.id, PaymentRequest.total_amount)
        .having(
            func.coalesce(func.sum(Payment.amount), 0) >= PaymentRequest.total_amount
        )
    )
    completed_rows = (await db.execute(completed_q)).all()
    completed_requests = len(completed_rows)

    return DashboardSummary(
        projects_active=projects_active,
        projects_closed=projects_closed,
        completed_requests=completed_requests,
        remaining_by_currency=remaining_by_currency,
        recent_payments=recent_payments,
    )
