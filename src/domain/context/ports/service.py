from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.schemas.context_layers import (
    LayerUsageDecision,
    SessionContextSnapshot,
    TenantKnowledgeContext,
    TenantKnowledgeQuery,
    UserMemoryContext,
    UserMemoryQuery,
)
from domain.context.schemas.memory_retrieval import (
    LayeredMemoryContext,
    MemoryRetrievalConfig,
)
from domain.context.schemas.memory_write import (
    MemoryWriteEventContext,
    MemoryWriteResult,
)
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.llm import LLMTaskType


class TenantKnowledgeRetrieverPort(Protocol):
    async def retrieve(
        self,
        *,
        query: TenantKnowledgeQuery,
        top_k_override: int | None = None,
        filters_override: dict[str, object] | None = None,
    ) -> TenantKnowledgeContext:
        pass


class UserMemoryReaderPort(Protocol):
    async def get_context(
        self,
        *,
        query: UserMemoryQuery,
        task_type: LLMTaskType | None = None,
        task_flags: AITaskContextFlags | None = None,
        tool_config_id: UUID | None = None,
        context_metadata: dict[str, object] | None = None,
        top_k_override: int | None = None,
    ) -> UserMemoryContext:
        pass

    async def get_preferences(self, *, tenant_id: UUID, user_id: str) -> dict:
        pass

    async def get_profile(self, *, tenant_id: UUID, user_id: str) -> dict:
        pass


class MemoryWriteServicePort(Protocol):
    async def write_memory_item(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        item: dict,
        event_context: MemoryWriteEventContext | None = None,
    ) -> MemoryWriteResult:
        pass


class SessionContextPort(Protocol):
    async def load_snapshot(self, *, flow_run_id: UUID) -> SessionContextSnapshot:
        pass

    async def persist_snapshot(self, *, snapshot: SessionContextSnapshot) -> None:
        pass


class MemoryRetrievalServicePort(Protocol):
    async def get_layered_context(
        self,
        *,
        execution_context: ExecutionContext | None,
        decision: LayerUsageDecision,
        task_type: LLMTaskType,
        user_input: str,
        tenant_id_for_knowledge: UUID | None = None,
        tenant_rag_config_id: UUID | None = None,
        user_id_for_memory: str | None = None,
        task_flags: AITaskContextFlags | None = None,
        tool_config_id: UUID | None = None,
        context_metadata: dict[str, object] | None = None,
        config: MemoryRetrievalConfig | None = None,
        tenant_top_k_override: int | None = None,
        tenant_filters_override: dict[str, object] | None = None,
        user_top_k_override: int | None = None,
    ) -> LayeredMemoryContext:
        pass
