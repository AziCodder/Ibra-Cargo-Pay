from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class CommentOut(BaseModel):
    id: int
    payment_request_id: int
    author_id: int
    author_login: str
    author_full_name: str
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}
