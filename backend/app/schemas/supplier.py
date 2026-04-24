from datetime import datetime

from pydantic import BaseModel


class SupplierCreate(BaseModel):
    full_name: str
    phone: str
    wechat_id: str
    document_1: str | None = None
    document_2: str | None = None
    document_3: str | None = None
    description: str | None = None


class SupplierUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    wechat_id: str | None = None
    document_1: str | None = None
    document_2: str | None = None
    document_3: str | None = None
    description: str | None = None


class SupplierOut(BaseModel):
    id: int
    full_name: str
    phone: str
    wechat_id: str
    document_1: str | None = None
    document_2: str | None = None
    document_3: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierBrief(BaseModel):
    id: int
    full_name: str

    model_config = {"from_attributes": True}


class SupplierListOut(BaseModel):
    items: list[SupplierOut]
    total: int
