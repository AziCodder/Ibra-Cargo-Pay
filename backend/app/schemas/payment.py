from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PaymentStatus = Literal["pending", "confirmed", "rejected"]


class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Сумма платежа")
    currency: str
    note: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v not in ("CNY", "USD", "RUB"):
            raise ValueError("Валюта должна быть CNY, USD или RUB")
        return v


class PaymentReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000, description="Причина отклонения")


class PaymentOut(BaseModel):
    id: int
    payment_request_id: int
    amount: Decimal
    currency: str
    note: str | None = None
    payment_date: date | None = None
    file_path: str | None = None
    file_name: str | None = None
    status: PaymentStatus = "pending"
    confirmed_by: int | None = None
    confirmed_at: datetime | None = None
    rejection_reason: str | None = None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}
