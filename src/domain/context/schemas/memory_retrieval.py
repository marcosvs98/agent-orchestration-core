from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from domain.context.schemas.context_layers import (
    SessionContextSnapshot,
    TenantKnowledgeContext,
    UserMemoryContext,
)


class TemporalTimestampSource(StrEnum):
    OBSERVED_AT = "OBSERVED_AT"
    CREATED_AT = "CREATED_AT"


class TemporalScoringConfig(BaseModel):
    enabled: bool = False
    half_life_seconds: int = 604800
    timestamp_source: TemporalTimestampSource = TemporalTimestampSource.OBSERVED_AT
    candidate_multiplier: int = 3


class MemoryRetrievalConfig(BaseModel):
    temporal_scoring: TemporalScoringConfig = Field(default_factory=TemporalScoringConfig)


class LayeredMemoryContext(BaseModel):
    session_context: SessionContextSnapshot | None = None
    tenant_knowledge_context: TenantKnowledgeContext | None = None
    user_memory_context: UserMemoryContext | None = None
