from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class EmbeddingStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EmbeddingJobPayload(BaseModel):
    tenant_id: UUID
    rag_config_id: UUID
    document_id: UUID
    flow_run_id: UUID | None = None
    session_id: UUID | None = None
    correlation_id: UUID | None = None
    user_id: str
    policy_version_id: UUID | None = None
    schema_id: str
    schema_version: int
    expires_at: str | None = None
    max_attempts: int = 3
