from datetime import datetime

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    full_name: str
    login: str
    password: str
    role: str
    description: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "client"):
            raise ValueError("Роль должна быть 'admin' или 'client'")
        return v


class UserUpdate(BaseModel):
    full_name: str | None = None
    login: str | None = None
    password: str | None = None
    role: str | None = None
    description: str | None = None
    telegram_chat_id: int | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("admin", "client"):
            raise ValueError("Роль должна быть 'admin' или 'client'")
        return v


class UserOut(BaseModel):
    id: int
    full_name: str
    login: str
    role: str
    description: str | None = None
    telegram_chat_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
