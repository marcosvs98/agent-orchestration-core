from uuid import uuid4

import pytest

from domain.execution.schemas.execution import FlowRunCreate
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine
from exceptions.service_exceptions import ResourceBlockedServiceException

from .conftest import make_execution_repository, stub_runtime_dependencies


@pytest.mark.asyncio
async def test_replay_produces_same_event_shape(mocker, idempotency):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()
    correlation_id = uuid4()

    repo = make_execution_repository(
        tenant_id=tenant_id, flow_id=flow_id, flow_version_id=flow_version_id
    )
    repo.create_interaction = mocker.AsyncMock(side_effect=[uuid4(), uuid4()])
    repo.create_flow_run = mocker.AsyncMock(side_effect=[uuid4(), uuid4()])

    lifecycle = RunLifecycleStateMachine()

    service = ExecutionService(
        repository=repo,
        idempotency=idempotency,
        lifecycle=lifecycle,
        limits=mocker.MagicMock(),
        tracer=mocker.MagicMock(),
    )
    stub_runtime_dependencies(service)

    payload = FlowRunCreate(
        flow_version_id=flow_version_id,
        session_id=session_id,
        user_id="test-user",
        input={"hello": "world"},
        correlation_id=correlation_id,
    )

    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/executions/flow-runs",
        idempotency_key="first",
        flow_run=payload,
    )
    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/executions/flow-runs",
        idempotency_key="second",
        flow_run=payload,
    )

    calls = service.hook.on_flow_start.call_args_list
    assert len(calls) == 2

    def _stable_part(payload: dict) -> dict:
        return {k: v for k, v in payload.items() if k not in {"interaction_id", "trace_id"}}

    assert _stable_part(calls[0].kwargs["payload"]) == _stable_part(calls[1].kwargs["payload"])
    assert calls[0].kwargs["tenant_id"] == calls[1].kwargs["tenant_id"]


@pytest.mark.asyncio
async def test_flow_run_blocks_without_active_pointer(mocker, idempotency):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()

    repo = make_execution_repository(
        tenant_id=tenant_id, flow_id=flow_id, flow_version_id=flow_version_id
    )
    repo.get_active_flow_version_id = mocker.AsyncMock(return_value=None)

    lifecycle = RunLifecycleStateMachine()

    service = ExecutionService(
        repository=repo,
        idempotency=idempotency,
        lifecycle=lifecycle,
        limits=mocker.MagicMock(),
        tracer=mocker.MagicMock(),
    )
    stub_runtime_dependencies(service)

    payload = FlowRunCreate(
        flow_version_id=flow_version_id, session_id=session_id, user_id="test-user"
    )

    with pytest.raises(ResourceBlockedServiceException, match="flow_not_active"):
        await service.create_flow_run(
            tenant_id=tenant_id,
            endpoint="/core/v1/executions/flow-runs",
            idempotency_key="no-active",
            flow_run=payload,
        )
