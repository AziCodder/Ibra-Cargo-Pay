from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NoteVisibility = Literal["private", "shared"]


class ProjectNoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    visibility: NoteVisibility = "private"


class ProjectNoteUpdate(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=8000)
    visibility: NoteVisibility | None = None


class ProjectNoteOut(BaseModel):
    id: int
    project_id: int
    content: str
    visibility: NoteVisibility
    created_by: int
    author_name: str
    created_at: datetime
    updated_at: datetime
    can_edit: bool = False

    model_config = {"from_attributes": True}
