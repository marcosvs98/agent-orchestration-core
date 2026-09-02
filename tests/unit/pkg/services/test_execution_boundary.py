from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.schemas.execution import FlowRunCreate, FlowRunInput
from services.execution_boundary import ExecutionBoundary


class TestExecutionBoundary:
    @pytest.mark.asyncio
    async def test_ingest_interaction_delegates_to_execution_service(self):
        execution_service = MagicMock()
        execution_service.create_flow_run = AsyncMock(return_value={"ok": True})

        orchestrator = MagicMock()
        access_policy_service = MagicMock()
        access_policy_service.authorize = AsyncMock()
        rate_limit_service = MagicMock()
        rate_limit_service.enforce = AsyncMock()
        boundary = ExecutionBoundary(
            execution_service=execution_service,
            agent_run_service=MagicMock(),
            tool_orchestrator=orchestrator,
            access_policy_service=access_policy_service,
            rate_limit_service=rate_limit_service,
        )

        await boundary.ingest_interaction_and_create_flow_run(
            auth=MagicMock(
                tenant_id=uuid4(),
                principal_type="machine",
                principal_id="p",
                scopes={"execution:flow_run:create"},
            ),
            endpoint="/core/v1/executions/flow-runs",
            idempotency_key="k",
            flow_run=FlowRunCreate(
                flow_version_id=uuid4(),
                session_id=uuid4(),
                user_id="test-user",
                input=FlowRunInput(user_input="hello"),
            ),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )

        access_policy_service.authorize.assert_called_once()
        rate_limit_service.enforce.assert_called_once()
        execution_service.create_flow_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_flow_run_applies_authorization_and_rate_limiting(self):
        from domain.execution.schemas.execution import FlowRun
        from domain.governance.schemas.scopes import Scope

        execution_service = MagicMock()
        execution_service.get_flow_run = AsyncMock(
            return_value=FlowRun(
                id=uuid4(),
                flow_version_id=uuid4(),
                session_id=uuid4(),
                user_id="test-user",
                status="COMPLETED",
                canonical_status="SUCCESS",
                correlation_id=uuid4(),
                input={},
                output={},
                error={},
            )
        )
        execution_service.repository = MagicMock()
        execution_service.repository.get_flow_context = AsyncMock(return_value=(uuid4(), uuid4()))

        orchestrator = MagicMock()
        access_policy_service = MagicMock()
        access_policy_service.authorize = AsyncMock()
        rate_limit_service = MagicMock()
        rate_limit_service.enforce = AsyncMock()

        boundary = ExecutionBoundary(
            execution_service=execution_service,
            agent_run_service=MagicMock(),
            tool_orchestrator=orchestrator,
            access_policy_service=access_policy_service,
            rate_limit_service=rate_limit_service,
        )

        tenant_id = uuid4()
        auth = MagicMock(
            tenant_id=tenant_id,
            principal_type="machine",
            principal_id="p",
            scopes={str(Scope.ExecutionFlowRunGet)},
        )
        execution_service.repository.get_flow_context.return_value = (
            uuid4(),
            tenant_id,
        )

        await boundary.get_flow_run(auth=auth, flow_run_id=str(uuid4()))

        rate_limit_service.enforce.assert_called_once()
        access_policy_service.authorize.assert_called_once()
        execution_service.get_flow_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_graph_state_applies_authorization_and_rate_limiting(self):
        from domain.execution.schemas.execution import GraphState
        from domain.governance.schemas.scopes import Scope

        execution_service = MagicMock()
        execution_service.get_graph_state = AsyncMock(
            return_value=GraphState(
                id=uuid4(), flow_run_id=uuid4(), state={}, last_node_run_id=None
            )
        )
        execution_service.repository = MagicMock()
        execution_service.repository.get_flow_context = AsyncMock(return_value=(uuid4(), uuid4()))

        orchestrator = MagicMock()
        access_policy_service = MagicMock()
        access_policy_service.authorize = AsyncMock()
        rate_limit_service = MagicMock()
        rate_limit_service.enforce = AsyncMock()

        boundary = ExecutionBoundary(
            execution_service=execution_service,
            agent_run_service=MagicMock(),
            tool_orchestrator=orchestrator,
            access_policy_service=access_policy_service,
            rate_limit_service=rate_limit_service,
        )

        tenant_id = uuid4()
        auth = MagicMock(
            tenant_id=tenant_id,
            principal_type="machine",
            principal_id="p",
            scopes={str(Scope.ExecutionGraphStateGet)},
        )
        execution_service.repository.get_flow_context.return_value = (
            uuid4(),
            tenant_id,
        )

        await boundary.get_graph_state(auth=auth, flow_run_id=str(uuid4()))

        rate_limit_service.enforce.assert_called_once()
        access_policy_service.authorize.assert_called_once()
        execution_service.get_graph_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_node_runs_applies_authorization_and_rate_limiting(self):
        from domain.governance.schemas.scopes import Scope

        execution_service = MagicMock()
        execution_service.list_node_runs = AsyncMock(return_value=[])

        orchestrator = MagicMock()
        access_policy_service = MagicMock()
        access_policy_service.authorize = AsyncMock()
        rate_limit_service = MagicMock()
        rate_limit_service.enforce = AsyncMock()

        boundary = ExecutionBoundary(
            execution_service=execution_service,
            agent_run_service=MagicMock(),
            tool_orchestrator=orchestrator,
            access_policy_service=access_policy_service,
            rate_limit_service=rate_limit_service,
        )

        tenant_id = uuid4()
        auth = MagicMock(
            tenant_id=tenant_id,
            principal_type="machine",
            principal_id="p",
            scopes={str(Scope.ExecutionNodeRunsList)},
        )

        result = await boundary.list_node_runs(auth=auth, flow_run_id=None, limit=200)

        assert result == []
        rate_limit_service.enforce.assert_called_once()
        access_policy_service.authorize.assert_called_once()
        execution_service.list_node_runs.assert_called_once_with(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

    @pytest.mark.asyncio
    async def test_list_agent_runs_applies_authorization_and_rate_limiting(self):
        from domain.governance.schemas.scopes import Scope

        execution_service = MagicMock()
        execution_service.list_agent_runs = AsyncMock(return_value=[])

        orchestrator = MagicMock()
        access_policy_service = MagicMock()
        access_policy_service.authorize = AsyncMock()
        rate_limit_service = MagicMock()
        rate_limit_service.enforce = AsyncMock()

        boundary = ExecutionBoundary(
            execution_service=execution_service,
            agent_run_service=MagicMock(),
            tool_orchestrator=orchestrator,
            access_policy_service=access_policy_service,
            rate_limit_service=rate_limit_service,
        )

        tenant_id = uuid4()
        auth = MagicMock(
            tenant_id=tenant_id,
            principal_type="machine",
            principal_id="p",
            scopes={str(Scope.ExecutionAgentRunsList)},
        )

        result = await boundary.list_agent_runs(auth=auth, flow_run_id=None, limit=200)

        assert result == []
        rate_limit_service.enforce.assert_called_once()
        access_policy_service.authorize.assert_called_once()
        execution_service.list_agent_runs.assert_called_once_with(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )
