from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from domain.context.schemas.context_layers import (
    ContextLayerScope,
    TenantKnowledgeContext,
    TenantKnowledgeQuery,
    UserMemoryContext,
    UserMemoryQuery,
    UserMemoryStructured,
)
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.schemas.rag_policy import RagActivationScope
from domain.governance.services.memory_policy_service import MemoryPolicyService
from domain.context.services.rag_activation_service import RagActivationService
from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.llm.schemas.llm import LLMTaskType
from domain.rag.services.rag_runtime_service import RagRuntimeService


class TenantKnowledgeRetriever:
    def __init__(self, rag_runtime_service: RagRuntimeService) -> None:
        self.rag_runtime_service = rag_runtime_service

    async def retrieve(
        self,
        *,
        query: TenantKnowledgeQuery,
        top_k_override: int | None = None,
        filters_override: dict[str, object] | None = None,
    ) -> TenantKnowledgeContext:
        effective_filters = {
            "scope": ContextLayerScope.TENANT_KNOWLEDGE.value,
        }
        if isinstance(filters_override, dict):
            effective_filters.update(filters_override)
        effective_filters["scope"] = ContextLayerScope.TENANT_KNOWLEDGE.value
        rag_context = await self.rag_runtime_service.get_context(
            tenant_id=query.tenant_id,
            rag_config_id=query.rag_config_id,
            user_input=query.user_input,
            filters_override=effective_filters,
            top_k_override=top_k_override,
        )
        return TenantKnowledgeContext(rag_context=rag_context)


class UserMemoryReader:
    def __init__(
        self,
        repository: ExecutionRepository,
        rag_runtime_service: RagRuntimeService | None = None,
        memory_policy_service: MemoryPolicyService | None = None,
        rag_activation_service: RagActivationService | None = None,
    ) -> None:
        self.repository = repository
        self.rag_runtime_service = rag_runtime_service
        self.memory_policy_service = memory_policy_service
        self.rag_activation_service = rag_activation_service

    async def get_preferences(self, *, tenant_id, user_id: str) -> dict:
        return await self.repository.get_user_preferences(
            tenant_id=tenant_id,
            user_id=user_id,
        )

    async def get_profile(self, *, tenant_id, user_id: str) -> dict:
        return await self.repository.get_user_memory_profile(
            tenant_id=tenant_id,
            user_id=user_id,
        )

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
        preferences = await self.get_preferences(
            tenant_id=query.tenant_id,
            user_id=query.user_id,
        )
        profile = await self.get_profile(
            tenant_id=query.tenant_id,
            user_id=query.user_id,
        )
        rag_context = None
        if self.rag_runtime_service and query.rag_config_id and query.user_input:
            filters_override = {
                "scope": ContextLayerScope.USER_MEMORY.value,
                "user_id": query.user_id,
            }
            effective_top_k_override = top_k_override
            if self.rag_activation_service and task_type:
                activation_decision = await self.rag_activation_service.decide(
                    tenant_id=query.tenant_id,
                    task_type=task_type,
                    scope=RagActivationScope.USER_MEMORY_VECTOR,
                    task_flags=task_flags,
                    rag_config_id=query.rag_config_id,
                    user_id=query.user_id,
                    user_input=query.user_input,
                    tool_config_id=tool_config_id,
                    context_metadata=context_metadata,
                )
                if not activation_decision.enabled:
                    return UserMemoryContext(
                        structured=UserMemoryStructured(
                            preferences=preferences,
                            profile=profile,
                        ),
                        rag_context=None,
                    )
                if effective_top_k_override is None:
                    effective_top_k_override = activation_decision.effective_top_k
                if isinstance(activation_decision.effective_filters_override, dict):
                    filters_override.update(activation_decision.effective_filters_override)
            if self.memory_policy_service:
                resolved_policy = await self.memory_policy_service.resolve(
                    tenant_id=query.tenant_id
                )
                if resolved_policy.definition is not None:
                    filters_override["expires_after"] = datetime.now(UTC).isoformat()
            filters_override["scope"] = ContextLayerScope.USER_MEMORY.value
            filters_override["user_id"] = query.user_id
            rag_context = await self.rag_runtime_service.get_context(
                tenant_id=query.tenant_id,
                rag_config_id=query.rag_config_id,
                user_id=query.user_id,
                user_input=query.user_input,
                filters_override=filters_override,
                top_k_override=effective_top_k_override,
            )
        return UserMemoryContext(
            structured=UserMemoryStructured(
                preferences=preferences,
                profile=profile,
            ),
            rag_context=rag_context,
        )
