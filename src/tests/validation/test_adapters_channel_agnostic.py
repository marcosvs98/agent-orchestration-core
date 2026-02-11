from types import SimpleNamespace
from uuid import uuid4

import pytest

from domain.execution.schemas.execution import FlowRunCreate
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine
from domain.execution.schemas.events import ExecutionEventType

from .test_runtime_determinism import FakeIdempotency  # reuse lightweight idempotency stub


@pytest.mark.asyncio
async def test_core_ignores_channel_variation(mocker):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()

    repo = mocker.MagicMock()
    repo.get_flow_version.return_value = SimpleNamespace(status="PUBLISHED", flow_id=flow_id)
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id)
    repo.get_active_flow_version_id.return_value = flow_version_id
    repo.create_interaction.side_effect = [uuid4(), uuid4()]
    repo.create_flow_run.side_effect = [uuid4(), uuid4()]
    repo.link_interaction_to_flow_run = mocker.AsyncMock()
    repo.append_execution_event = mocker.AsyncMock()

    service = ExecutionService(
        repository=repo,
        idempotency=FakeIdempotency(),
        lifecycle=RunLifecycleStateMachine(),
        limits=mocker.MagicMock(),
    )
    service.llm_executor = mocker.MagicMock()

    payload = FlowRunCreate(
        flow_version_id=flow_version_id, session_id=session_id, user_id="test-user"
    )

    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/flow-runs",
        idempotency_key="http",
        flow_run=payload,
        channel="http",
    )
    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/flow-runs",
        idempotency_key="whatsapp",
        flow_run=payload,
        channel="whatsapp",
    )

    calls = repo.append_execution_event.call_args_list
    assert len(calls) == 2
    assert all(call.kwargs["event_type"] == ExecutionEventType.FlowStarted for call in calls)
    channels = [call.kwargs["payload"]["channel"] for call in calls]
    assert set(channels) == {"http", "whatsapp"}
