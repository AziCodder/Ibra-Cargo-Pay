from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    status: str = "active"

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("active", "closed"):
            raise ValueError("Статус должен быть 'active' или 'closed'")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("active", "closed"):
            raise ValueError("Статус должен быть 'active' или 'closed'")
        return v


class UserBrief(BaseModel):
    id: int
    full_name: str
    login: str

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: int
    project_number: int
    name: str
    description: str | None = None
    client_id: int | None = None
    client: UserBrief | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListOut(BaseModel):
    items: list[ProjectOut]
    total: int


class CurrencySummary(BaseModel):
    currency: str
    total: Decimal
    invoiced: Decimal = Decimal("0")   # выставлено счетов (сумма по заявкам)
    paid: Decimal
    remaining: Decimal
    commission: Decimal | None = None


class ProjectSummary(BaseModel):
    currencies: list[CurrencySummary]
