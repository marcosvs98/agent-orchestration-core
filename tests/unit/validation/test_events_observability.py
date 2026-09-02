from uuid import uuid4

import pytest

from domain.execution.schemas.execution import FlowRunCreate
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine

from .conftest import make_execution_repository, stub_runtime_dependencies


@pytest.mark.asyncio
async def test_execution_event_contains_correlation_and_channel(mocker, idempotency):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()
    correlation_id = uuid4()

    repo = make_execution_repository(
        tenant_id=tenant_id, flow_id=flow_id, flow_version_id=flow_version_id
    )

    service = ExecutionService(
        repository=repo,
        idempotency=idempotency,
        lifecycle=RunLifecycleStateMachine(),
        limits=mocker.MagicMock(),
        tracer=mocker.MagicMock(),
    )
    stub_runtime_dependencies(service)

    payload = FlowRunCreate(
        flow_version_id=flow_version_id,
        session_id=session_id,
        user_id="test-user",
        correlation_id=correlation_id,
    )

    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/executions/flow-runs",
        idempotency_key="evt",
        flow_run=payload,
        channel="http",
        headers={"x-test": "1"},
    )

    service.hook.on_flow_start.assert_awaited_once()
    call = service.hook.on_flow_start.call_args
    assert call.kwargs["correlation_id"] == correlation_id
    assert call.kwargs["tenant_id"] == tenant_id
    assert call.kwargs["payload"]["channel"] == "http"
    assert call.kwargs["payload"]["interaction_id"]
    assert call.kwargs["payload"]["trace_id"]
