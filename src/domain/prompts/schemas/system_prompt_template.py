from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SystemPromptTemplate(BaseModel):
    id: UUID
    name: str
    template_text: str
    allowed_placeholders: list[str] | None = None
    version: int
    status: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": True}
