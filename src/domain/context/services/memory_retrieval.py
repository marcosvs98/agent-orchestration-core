from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.ports.service import (
    SessionContextPort,
    TenantKnowledgeRetrieverPort,
    UserMemoryReaderPort,
)
from domain.context.schemas.context_layers import (
    LayerUsageDecision,
    TenantKnowledgeQuery,
    UserMemoryContext,
    UserMemoryQuery,
)
from domain.context.schemas.memory_retrieval import (
    LayeredMemoryContext,
    MemoryRetrievalConfig,
    TemporalTimestampSource,
)
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.llm import LLMTaskType
from domain.rag.schemas.rag import RagContext, RagContextItem


class MemoryRetrievalService:
    def __init__(
        self,
        *,
        tenant_knowledge_retriever: TenantKnowledgeRetrieverPort | None,
        user_memory_reader: UserMemoryReaderPort | None,
        session_context_service: SessionContextPort | None,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.tenant_knowledge_retriever = tenant_knowledge_retriever
        self.user_memory_reader = user_memory_reader
        self.session_context_service = session_context_service
        self.tracer = tracer

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
        retrieval_config = config or MemoryRetrievalConfig()

        session_context = None
        if (
            decision.allow_session_context
            and self.session_context_service is not None
            and execution_context is not None
        ):
            session_context = await self.session_context_service.load_snapshot(
                flow_run_id=execution_context.flow_run_id
            )

        tenant_knowledge_context = None
        if (
            decision.allow_tenant_knowledge
            and self.tenant_knowledge_retriever is not None
            and tenant_id_for_knowledge is not None
            and tenant_rag_config_id is not None
            and user_input
        ):
            tenant_knowledge_context = await self.tenant_knowledge_retriever.retrieve(
                query=TenantKnowledgeQuery(
                    tenant_id=tenant_id_for_knowledge,
                    rag_config_id=tenant_rag_config_id,
                    user_input=user_input,
                ),
                top_k_override=tenant_top_k_override,
                filters_override=tenant_filters_override,
            )

        user_memory_context = None
        if (
            decision.allow_user_memory_structured
            and self.user_memory_reader is not None
            and execution_context is not None
            and user_id_for_memory is not None
        ):
            base_top_k = user_top_k_override
            candidate_top_k = user_top_k_override
            temporal_enabled = (
                decision.allow_user_memory_vector and retrieval_config.temporal_scoring.enabled
            )
            if temporal_enabled and base_top_k is not None:
                multiplier = max(
                    1,
                    int(retrieval_config.temporal_scoring.candidate_multiplier),
                )
                candidate_top_k = base_top_k * multiplier
            user_memory_context = await self.user_memory_reader.get_context(
                query=UserMemoryQuery(
                    tenant_id=execution_context.tenant_id,
                    user_id=user_id_for_memory,
                    rag_config_id=tenant_rag_config_id
                    if decision.allow_user_memory_vector
                    else None,
                    user_input=user_input if decision.allow_user_memory_vector else "",
                ),
                task_type=task_type,
                task_flags=task_flags,
                tool_config_id=tool_config_id,
                context_metadata=context_metadata,
                top_k_override=candidate_top_k,
            )
            if temporal_enabled and user_memory_context.rag_context is not None:
                user_memory_context = UserMemoryContext(
                    structured=user_memory_context.structured,
                    rag_context=self._rerank_with_temporal_decay(
                        rag_context=user_memory_context.rag_context,
                        base_top_k=base_top_k,
                        timestamp_source=retrieval_config.temporal_scoring.timestamp_source,
                        half_life_seconds=retrieval_config.temporal_scoring.half_life_seconds,
                    ),
                )

        result = LayeredMemoryContext(
            session_context=session_context,
            tenant_knowledge_context=tenant_knowledge_context,
            user_memory_context=user_memory_context,
        )

        return result

    def _rerank_with_temporal_decay(
        self,
        *,
        rag_context: RagContext,
        base_top_k: int | None,
        timestamp_source: TemporalTimestampSource,
        half_life_seconds: int,
    ) -> RagContext:
        if not rag_context.context_items:
            return rag_context
        normalized_half_life = max(1, int(half_life_seconds))
        now = datetime.now(UTC)
        rescored: list[RagContextItem] = []
        for item in rag_context.context_items:
            timestamp = self._resolve_timestamp(
                item=item,
                timestamp_source=timestamp_source,
            )
            if timestamp is None:
                rescored.append(item)
                continue
            age_seconds = max(0.0, (now - timestamp).total_seconds())
            weight = math.exp(-age_seconds / normalized_half_life)
            rescored.append(
                item.model_copy(
                    update={"score": float(item.score) * weight},
                )
            )
        ordered = sorted(rescored, key=lambda item: float(item.score), reverse=True)
        if base_top_k is not None and base_top_k > 0:
            ordered = ordered[:base_top_k]
        return RagContext(
            context_items=ordered,
            context_summary=rag_context.context_summary,
            eligible=rag_context.eligible,
            reason=rag_context.reason,
            generation_contract=rag_context.generation_contract,
        )

    def _resolve_timestamp(
        self,
        *,
        item: RagContextItem,
        timestamp_source: TemporalTimestampSource,
    ) -> datetime | None:
        if timestamp_source == TemporalTimestampSource.CREATED_AT:
            return self._ensure_utc(item.created_at) or self._ensure_utc(item.observed_at)
        return self._ensure_utc(item.observed_at) or self._ensure_utc(item.created_at)

    def _ensure_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
