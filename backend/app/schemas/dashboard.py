from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CurrencyBalance(BaseModel):
    currency: str
    total: Decimal
    paid: Decimal
    remaining: Decimal


class RecentPaymentOut(BaseModel):
    id: int
    payment_request_id: int
    project_id: int
    project_name: str
    project_number: int
    amount: Decimal
    currency: str
    note: str | None = None
    created_by: int
    created_by_full_name: str
    created_at: datetime


class DashboardSummary(BaseModel):
    projects_active: int
    projects_closed: int
    completed_requests: int
    remaining_by_currency: list[CurrencyBalance]
    recent_payments: list[RecentPaymentOut]
