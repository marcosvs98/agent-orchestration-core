from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ToolCatalogDocument(BaseModel):
    tool_id: UUID
    tool_config_id: UUID
    tool_name: str | None = None
    operation_id: str | None = None
    method: str | None = None
    path: str | None = None
    summary: str | None = None
    description: str | None = None
    request_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)
    version: str | None = None


class ToolDiscoveryCandidate(BaseModel):
    tool_config_id: UUID
    score: float
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
