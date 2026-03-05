from types import SimpleNamespace
from uuid import uuid4

import pytest

from domain.execution.schemas.execution import FlowRunCreate
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine
from domain.execution.schemas.events import ExecutionEventType
from .test_runtime_determinism import FakeIdempotency


@pytest.mark.asyncio
async def test_execution_event_contains_correlation_and_channel(mocker):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()
    correlation_id = uuid4()

    repo = mocker.MagicMock()
    repo.get_flow_version.return_value = SimpleNamespace(status="PUBLISHED", flow_id=flow_id)
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id)
    repo.get_active_flow_version_id.return_value = flow_version_id
    repo.create_interaction.return_value = uuid4()
    repo.create_flow_run.return_value = uuid4()
    repo.link_interaction_to_flow_run = mocker.AsyncMock()
    repo.append_execution_event = mocker.AsyncMock()

    service = ExecutionService(
        repository=repo,
        idempotency=FakeIdempotency(),
        lifecycle=RunLifecycleStateMachine(),
        limits=mocker.MagicMock(),
        tracer=mocker.MagicMock(),
    )
    service.llm_executor = mocker.MagicMock()

    payload = FlowRunCreate(
        flow_version_id=flow_version_id,
        session_id=session_id,
        user_id="test-user",
        correlation_id=correlation_id,
    )

    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/flow-runs",
        idempotency_key="evt",
        flow_run=payload,
        channel="http",
        headers={"x-test": "1"},
    )

    repo.append_execution_event.assert_called_once()
    call = repo.append_execution_event.call_args
    assert call.kwargs["event_type"] == ExecutionEventType.FlowStarted
    assert call.kwargs["correlation_id"] == correlation_id
    assert call.kwargs["payload"]["channel"] == "http"
