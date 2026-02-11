from uuid import UUID

from pydantic import BaseModel

from domain.agents.schemas.agents import PersonaConfig
from domain.context.schemas.context_layers import (
    SessionContextSnapshot,
    TenantKnowledgeContext,
    UserMemoryContext,
)
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.rag.schemas.rag import RagContext


class IntentDetectionContext(BaseModel):
    persona: PersonaConfig
    user_input: str
    context: ExecutionContext
    session_context: SessionContextSnapshot | None = None
    user_memory_context: UserMemoryContext | None = None
    tenant_knowledge_context: TenantKnowledgeContext | None = None


class SlotFillingContext(BaseModel):
    persona: PersonaConfig
    intent: str
    user_input: str
    tool_config_id: UUID
    request_schema: dict
    session_context: SessionContextSnapshot | None = None
    user_memory_context: UserMemoryContext | None = None
    tenant_knowledge_context: TenantKnowledgeContext | None = None


class ResponseFormattingContext(BaseModel):
    persona: PersonaConfig
    tool_response: dict
    original_intent: str
    user_input: str
    rag_context: RagContext | None = None
    session_context: SessionContextSnapshot | None = None
    user_memory_context: UserMemoryContext | None = None
    tenant_knowledge_context: TenantKnowledgeContext | None = None


class ClarificationContext(BaseModel):
    persona: PersonaConfig
    intent: str
    missing_fields: list[str]
    session_context: SessionContextSnapshot | None = None
