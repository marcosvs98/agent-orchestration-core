from uuid import uuid4

import pytest

from domain.execution.schemas.execution import FlowRunCreate
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine

from .conftest import make_execution_repository, stub_runtime_dependencies


@pytest.mark.asyncio
async def test_core_ignores_channel_variation(mocker, idempotency):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()

    repo = make_execution_repository(
        tenant_id=tenant_id, flow_id=flow_id, flow_version_id=flow_version_id
    )
    repo.create_interaction = mocker.AsyncMock(side_effect=[uuid4(), uuid4()])
    repo.create_flow_run = mocker.AsyncMock(side_effect=[uuid4(), uuid4()])

    service = ExecutionService(
        repository=repo,
        idempotency=idempotency,
        lifecycle=RunLifecycleStateMachine(),
        limits=mocker.MagicMock(),
        tracer=mocker.MagicMock(),
    )
    stub_runtime_dependencies(service)

    payload = FlowRunCreate(
        flow_version_id=flow_version_id, session_id=session_id, user_id="test-user"
    )

    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/executions/flow-runs",
        idempotency_key="http",
        flow_run=payload,
        channel="http",
    )
    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/executions/flow-runs",
        idempotency_key="whatsapp",
        flow_run=payload,
        channel="whatsapp",
    )

    calls = service.hook.on_flow_start.call_args_list
    assert len(calls) == 2
    assert [call.kwargs["payload"]["channel"] for call in calls] == ["http", "whatsapp"]
    channels = [call.kwargs["payload"]["channel"] for call in calls]
    assert set(channels) == {"http", "whatsapp"}
