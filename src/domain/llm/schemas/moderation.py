from __future__ import annotations

from pydantic import BaseModel, Field


class ModerationResult(BaseModel):
    flagged: bool = Field(...)
    categories: dict[str, dict[str, bool | float]] = Field(default_factory=dict)
