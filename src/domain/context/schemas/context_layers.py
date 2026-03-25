from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from domain.rag.schemas.rag import RagContext


class ContextLayerScope(StrEnum):
    TENANT_KNOWLEDGE = "TENANT_KNOWLEDGE"
    USER_MEMORY = "USER_MEMORY"
    SESSION_CONTEXT = "SESSION_CONTEXT"


class TenantKnowledgeQuery(BaseModel):
    tenant_id: UUID
    rag_config_id: UUID
    user_input: str


class TenantKnowledgeContext(BaseModel):
    scope: ContextLayerScope = ContextLayerScope.TENANT_KNOWLEDGE
    rag_context: RagContext | None = None


class UserMemoryQuery(BaseModel):
    tenant_id: UUID
    user_id: str
    rag_config_id: UUID | None = None
    user_input: str


class UserMemoryStructured(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)


class UserMemoryContext(BaseModel):
    scope: ContextLayerScope = ContextLayerScope.USER_MEMORY
    structured: UserMemoryStructured = Field(default_factory=UserMemoryStructured)
    rag_context: RagContext | None = None


class SessionContextSnapshot(BaseModel):
    flow_run_id: UUID
    current_node_id: str | None = None
    resume_to_node_id: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    memory: list[dict[str, Any]] = Field(default_factory=list)


class LayerUsageDecision(BaseModel):
    allow_session_context: bool = False
    allow_tenant_knowledge: bool = False
    allow_user_memory_structured: bool = False
    allow_user_memory_vector: bool = False
    allow_memory_write: bool = False

    @classmethod
    def from_ai_task_flags(
        cls,
        *,
        allow_rag_tenant: bool,
        allow_user_memory_structured: bool,
        allow_user_memory_vector: bool,
        allow_session_context: bool,
        allow_memory_write: bool,
    ) -> "LayerUsageDecision":
        return cls(
            allow_session_context=allow_session_context,
            allow_tenant_knowledge=allow_rag_tenant,
            allow_user_memory_structured=allow_user_memory_structured,
            allow_user_memory_vector=allow_user_memory_vector,
            allow_memory_write=allow_memory_write,
        )
