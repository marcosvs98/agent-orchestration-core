from __future__ import annotations

from uuid import UUID

from domain.governance.repositories.runtime_policy_repository import RuntimePolicyRepository
from domain.governance.schemas.runtime_policy import (
    ResolvedRuntimePolicy,
    RuntimePolicyDefinition,
    RuntimePolicyScope,
    RuntimePolicySource,
)


class RuntimePolicyResolver:
    """Resolves runtime policy with precedence FLOW -> TENANT -> DEFAULT."""

    def __init__(self, repository: RuntimePolicyRepository, default_policy: dict) -> None:
        self.repository = repository
        self.default_policy = default_policy

    async def resolve(self, *, tenant_id: UUID, flow_id: UUID | None) -> ResolvedRuntimePolicy:
        if flow_id:
            flow_policy = await self.repository.get_active_flow_policy(tenant_id=tenant_id, flow_id=flow_id)
            if flow_policy:
                return ResolvedRuntimePolicy(
                    source=RuntimePolicySource.FLOW,
                    runtime_policy_id=flow_policy.runtime_policy_id,
                    version=flow_policy.version,
                    definition=RuntimePolicyDefinition.model_validate(flow_policy.policy_definition),
                    scope=RuntimePolicyScope.FLOW,
                    flow_id=flow_id,
                )
        tenant_policy = await self.repository.get_active_tenant_policy(tenant_id=tenant_id)
        if tenant_policy:
            return ResolvedRuntimePolicy(
                source=RuntimePolicySource.TENANT,
                runtime_policy_id=tenant_policy.runtime_policy_id,
                version=tenant_policy.version,
                definition=RuntimePolicyDefinition.model_validate(tenant_policy.policy_definition),
                scope=RuntimePolicyScope.TENANT,
                flow_id=tenant_policy.flow_id,
            )
        # Default system policy (immutable)
        return ResolvedRuntimePolicy(
            source=RuntimePolicySource.DEFAULT,
            runtime_policy_id=None,
            version=str(self.default_policy.get("version", "1")),
            definition=RuntimePolicyDefinition.model_validate(self.default_policy.get("policy_definition", {})),
            scope=RuntimePolicyScope.TENANT,
            flow_id=None,
        )
