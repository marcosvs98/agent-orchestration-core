from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

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
            tool_orchestrator=orchestrator,
            access_policy_service=access_policy_service,
            rate_limit_service=rate_limit_service,
        )

        await boundary.ingest_interaction_and_create_flow_run(
            auth=MagicMock(tenant_id=uuid4(), principal_type="machine", principal_id="p", scopes={"execution:flow_run:create"}),
            endpoint="/core/v1/executions/flow-runs",
            idempotency_key="k",
            payload=MagicMock(),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )

        access_policy_service.authorize.assert_called_once()
        rate_limit_service.enforce.assert_called_once()
        execution_service.create_flow_run.assert_called_once()
