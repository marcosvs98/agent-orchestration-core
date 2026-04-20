import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.governance.services.access_policy_service import AccessPolicyService
from domain.governance.services.execution_limit_service import ExecutionLimitService
from exceptions.service_exceptions import AuthorizationDeniedException, LimitExceededException


def _tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


class TestAccessPolicyService:
    @pytest.mark.asyncio
    async def test_authorize_denies_when_not_configured(self):
        repo = MagicMock()
        repo.get_default_policy_for_tenant = AsyncMock(return_value=None)
        service = AccessPolicyService(repository=repo, tracer=_tracer())
        with pytest.raises(AuthorizationDeniedException):
            await service.authorize(
                tenant_id=uuid4(),
                principal_type="machine",
                principal_id="p",
                scopes={"execution:flow_run:create"},
                action="execution:flow_run:create",
            )

    @pytest.mark.asyncio
    async def test_authorize_allows_when_action_allowed_and_scope_present(self):
        policy_id = uuid4()
        policy = MagicMock()
        policy.access_policy_id = policy_id
        policy.to_dict = MagicMock(return_value={"access_policy_id": str(policy_id)})
        pv = MagicMock()
        pv.rules = {"allow": ["execution:flow_run:create"]}
        pv.to_dict = MagicMock(return_value={"rules": pv.rules})
        repo = MagicMock()
        repo.get_default_policy_for_tenant = AsyncMock(return_value=policy)
        repo.get_published_policy_version = AsyncMock(return_value=pv)
        service = AccessPolicyService(repository=repo, tracer=_tracer())
        await service.authorize(
            tenant_id=uuid4(),
            principal_type="machine",
            principal_id="p",
            scopes={"execution:flow_run:create"},
            action="execution:flow_run:create",
        )


class TestExecutionLimitService:
    @pytest.mark.asyncio
    async def test_limits_raise_when_tool_runs_exceeded(self):
        tenant_id = uuid4()
        policy_repo = MagicMock()
        policy_repo.get_default_policy_for_tenant = AsyncMock(
            return_value=SimpleNamespace(execution_limit_policy_id=uuid4())
        )
        policy_repo.get_published_policy_version = AsyncMock(
            return_value=SimpleNamespace(
                status="PUBLISHED",
                max_agent_runs_per_interaction=100,
                max_tool_runs_per_flow_run=1,
            )
        )
        exec_repo = MagicMock()
        exec_repo.count_tool_runs_for_flow_run = AsyncMock(return_value=1)
        exec_repo.count_agent_runs_for_flow_run = AsyncMock(return_value=0)
        service = ExecutionLimitService(policy_repository=policy_repo, execution_repository=exec_repo)
        with pytest.raises(LimitExceededException):
            await service.assert_can_create_tool_run(tenant_id=tenant_id, flow_run_id=uuid4())
