from __future__ import annotations

from uuid import UUID

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.schemas.rag_policy import (
    RagActivationScope,
    RagPolicyDefinition,
    RagScopePolicy,
    RagTaskDefaults,
    ResolvedRagPolicy,
    ResolvedRagPolicySource,
)
from domain.llm.schemas.llm import LLMTaskType


class RagPolicyService:
    def __init__(self, repository: ExecutionRepository) -> None:
        self.repository = repository

    async def resolve(self, *, tenant_id: UUID) -> ResolvedRagPolicy:
        policy_version_id = await self.repository.get_active_rag_policy_version_id(tenant_id)
        if policy_version_id is None:
            return ResolvedRagPolicy(
                source=ResolvedRagPolicySource.DEFAULT_NONE,
                tenant_id=tenant_id,
                policy_version_id=None,
                definition=None,
            )
        policy_version = await self.repository.get_rag_policy_version(policy_version_id)
        if policy_version is None:
            return ResolvedRagPolicy(
                source=ResolvedRagPolicySource.DEFAULT_NONE,
                tenant_id=tenant_id,
                policy_version_id=None,
                definition=None,
            )
        definition = RagPolicyDefinition.model_validate(policy_version.policy_definition or {})
        return ResolvedRagPolicy(
            source=ResolvedRagPolicySource.TENANT_ACTIVE,
            tenant_id=tenant_id,
            policy_version_id=policy_version.rag_policy_version_id,
            definition=definition,
        )

    async def scope_policy(
        self,
        *,
        tenant_id: UUID,
        task_type: LLMTaskType,
        scope: RagActivationScope,
    ) -> tuple[ResolvedRagPolicy, RagScopePolicy | None]:
        resolved = await self.resolve(tenant_id=tenant_id)
        if resolved.definition is None:
            return resolved, None
        task_defaults = resolved.definition.defaults.get(task_type, RagTaskDefaults())
        if scope == RagActivationScope.TENANT_KNOWLEDGE:
            return resolved, task_defaults.tenant_knowledge
        return resolved, task_defaults.user_memory_vector

    def cap_top_k(
        self,
        *,
        top_k: int,
        resolved_policy: ResolvedRagPolicy,
    ) -> int:
        definition = resolved_policy.definition
        if definition is None or definition.top_k_cap is None:
            return top_k
        return min(top_k, int(definition.top_k_cap))
