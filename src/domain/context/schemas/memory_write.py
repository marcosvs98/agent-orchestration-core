from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from domain.governance.schemas.memory_policy import MemoryWriteTarget


class MemoryWriteEventContext(BaseModel):
    session_id: UUID | None = None
    flow_run_id: UUID | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    node_id: UUID | None = None


class MemoryWriteResult(BaseModel):
    targets_applied: list[MemoryWriteTarget] = Field(default_factory=list)
    policy_version_id: UUID | None = None
    preference_version: int | None = None
    profile_version: int | None = None
    embedded_document_id: UUID | None = None
