from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ProjectItemCreate(BaseModel):
    name: str
    details: str | None = None
    quantity: Decimal = Field(..., gt=0, description="Количество")
    supplier_id: int | None = None
    price: Decimal = Field(..., ge=0, description="Цена")
    cost_price: Decimal = Field(..., ge=0, description="Себестоимость")
    currency: str
    commission: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Комиссия %")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v not in ("CNY", "USD", "RUB"):
            raise ValueError("Валюта должна быть CNY, USD или RUB")
        return v


class ProjectItemUpdate(BaseModel):
    name: str | None = None
    details: str | None = None
    quantity: Decimal | None = None
    supplier_id: int | None = None
    price: Decimal | None = None
    cost_price: Decimal | None = None
    currency: str | None = None
    commission: Decimal | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is not None and v not in ("CNY", "USD", "RUB"):
            raise ValueError("Валюта должна быть CNY, USD или RUB")
        return v


class SupplierBrief(BaseModel):
    id: int
    full_name: str

    model_config = {"from_attributes": True}


class RequirementOut(BaseModel):
    id: int
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RequirementCreate(BaseModel):
    text: str


# Клиентская схема — без cost_price
class ProjectItemClientOut(BaseModel):
    id: int
    project_id: int
    name: str
    details: str | None = None
    quantity: Decimal
    supplier_id: int | None = None
    supplier: SupplierBrief | None = None
    price: Decimal
    currency: str
    commission: Decimal
    requirements: list[RequirementOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Админская схема — включает cost_price
class ProjectItemAdminOut(ProjectItemClientOut):
    cost_price: Decimal
