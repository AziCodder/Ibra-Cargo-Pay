from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


ALLOWED_PRIORITIES = ("urgent", "normal", "deferred")


class PaymentRequestItemIn(BaseModel):
    project_item_id: int
    amount: Decimal = Field(..., gt=0, description="Сумма по позиции")


class PaymentRequestCreate(BaseModel):
    items: list[PaymentRequestItemIn]
    total_amount: Decimal = Field(..., gt=0, description="Общая сумма заявки")
    currency: str
    requisites: str | None = None
    payment_details: str | None = None
    due_date: date | None = None
    priority: str = "normal"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v not in ("CNY", "USD", "RUB"):
            raise ValueError("Валюта должна быть CNY, USD или RUB")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ALLOWED_PRIORITIES:
            raise ValueError("Приоритет должен быть urgent, normal или deferred")
        return v


class PaymentRequestUpdate(BaseModel):
    total_amount: Decimal | None = None
    currency: str | None = None
    requisites: str | None = None
    payment_details: str | None = None
    due_date: date | None = None
    priority: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is not None and v not in ("CNY", "USD", "RUB"):
            raise ValueError("Валюта должна быть CNY, USD или RUB")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_PRIORITIES:
            raise ValueError("Приоритет должен быть urgent, normal или deferred")
        return v


class PaymentRequestItemOut(BaseModel):
    id: int
    project_item_id: int
    project_item_name: str
    amount: Decimal

    model_config = {"from_attributes": True}


class AttachmentOut(BaseModel):
    id: int
    file_path: str
    file_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentShortOut(BaseModel):
    id: int
    amount: Decimal
    currency: str
    note: str | None = None
    payment_date: date | None = None
    file_path: str | None = None
    file_name: str | None = None
    status: str = "pending"
    confirmed_by: int | None = None
    confirmed_at: datetime | None = None
    rejection_reason: str | None = None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentRequestOut(BaseModel):
    id: int
    project_id: int
    total_amount: Decimal
    currency: str
    requisites: str | None = None
    payment_details: str | None = None
    due_date: date | None = None
    priority: str
    remaining_amount: Decimal
    items: list[PaymentRequestItemOut] = []
    attachments: list[AttachmentOut] = []
    payments: list[PaymentShortOut] = []
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentRequestListOut(BaseModel):
    id: int
    project_id: int
    total_amount: Decimal
    currency: str
    due_date: date | None = None
    priority: str
    remaining_amount: Decimal
    items_names: str  # "Товар1, Товар2"
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}
