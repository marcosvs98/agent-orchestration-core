from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserPrompt(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    content: str
    version: int
    is_active: bool
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class UserPromptCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    created_by: str | None = None
