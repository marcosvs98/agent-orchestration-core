from uuid import UUID

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.ports.execution_limit_service import ExecutionLimitServicePort
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from exceptions.service_exceptions import LimitExceededException, AuthorizationDeniedException
from domain.common.schemas.versioning import VersionStatus


class ExecutionLimitService(ExecutionLimitServicePort):
    def __init__(
        self,
        policy_repository: ExecutionLimitPolicyRepository,
        execution_repository: ExecutionRepository,
    ) -> None:
        self.policy_repository = policy_repository
        self.execution_repository = execution_repository

    async def _get_limits(self, tenant_id: UUID):
        policy = await self.policy_repository.get_default_policy_for_tenant(tenant_id)
        if policy is None:
            raise AuthorizationDeniedException(message="execution_limit_policy_not_configured")
        version = await self.policy_repository.get_published_policy_version(
            policy.execution_limit_policy_id
        )
        if version is None or version.status != VersionStatus.PUBLISHED:
            raise AuthorizationDeniedException(message="execution_limit_policy_not_published")
        return version

    async def assert_can_create_agent_run(self, *, tenant_id: UUID, flow_run_id: UUID) -> None:
        limits = await self._get_limits(tenant_id)
        current = await self.execution_repository.count_agent_runs_for_flow_run(flow_run_id)
        if current >= int(limits.max_agent_runs_per_interaction):
            raise LimitExceededException(message="max_agent_runs_exceeded")

    async def assert_can_create_tool_run(self, *, tenant_id: UUID, flow_run_id: UUID) -> None:
        limits = await self._get_limits(tenant_id)
        current = await self.execution_repository.count_tool_runs_for_flow_run(flow_run_id)
        if current >= int(limits.max_tool_runs_per_flow_run):
            raise LimitExceededException(message="max_tool_runs_exceeded")
