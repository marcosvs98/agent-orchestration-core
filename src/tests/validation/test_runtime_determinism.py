from types import SimpleNamespace
from uuid import uuid4, UUID

import pytest

from domain.execution.schemas.execution import FlowRunCreate
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.schemas.events import ExecutionEventType
from exceptions.service_exceptions import ResourceBlockedServiceException


class FakeIdempotency(IdempotencyService):
    def __init__(self):
        # bypass Redis dependency for validation tests
        self.store: dict[str, dict] = {}

    def build_key(self, tenant_id: UUID, endpoint: str, idempotency_key: str) -> str:  # type: ignore[override]
        return f"{tenant_id}:{endpoint}:{idempotency_key}"

    async def try_acquire(self, key: str) -> bool:  # type: ignore[override]
        return key not in self.store

    async def get(self, key: str) -> dict | None:  # type: ignore[override]
        return self.store.get(key)

    async def set_result(self, key: str, result: dict) -> None:  # type: ignore[override]
        self.store[key] = result


@pytest.mark.asyncio
async def test_replay_produces_same_event_shape(mocker):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()
    correlation_id = uuid4()

    # repository mocks
    repo = mocker.MagicMock()
    repo.get_flow_version.return_value = SimpleNamespace(status="PUBLISHED", flow_id=flow_id)
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id)
    repo.get_active_flow_version_id.return_value = flow_version_id
    repo.create_interaction.side_effect = [uuid4(), uuid4()]
    repo.create_flow_run.side_effect = [uuid4(), uuid4()]
    repo.link_interaction_to_flow_run = mocker.AsyncMock()
    repo.append_execution_event = mocker.AsyncMock()

    lifecycle = RunLifecycleStateMachine()
    idempotency = FakeIdempotency()

    service = ExecutionService(
        repository=repo,
        idempotency=idempotency,
        lifecycle=lifecycle,
        limits=mocker.MagicMock(),
    )

    payload = FlowRunCreate(
        flow_version_id=flow_version_id,
        session_id=session_id,
        input={"hello": "world"},
        correlation_id=correlation_id,
    )

    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/flow-runs",
        idempotency_key="first",
        payload=payload,
    )
    await service.create_flow_run(
        tenant_id=tenant_id,
        endpoint="/core/v1/flow-runs",
        idempotency_key="second",
        payload=payload,
    )

    calls = repo.append_execution_event.call_args_list
    assert len(calls) == 2
    assert all(call.kwargs["event_type"] == ExecutionEventType.FlowStarted for call in calls)
    # Payloads should carry the same logical content for the same input
    assert calls[0].kwargs["payload"] == calls[1].kwargs["payload"]


@pytest.mark.asyncio
async def test_flow_run_blocks_without_active_pointer(mocker):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    session_id = uuid4()

    repo = mocker.MagicMock()
    repo.get_flow_version.return_value = SimpleNamespace(status="PUBLISHED", flow_id=flow_id)
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id)
    repo.get_active_flow_version_id.return_value = None

    lifecycle = RunLifecycleStateMachine()
    idempotency = FakeIdempotency()

    service = ExecutionService(
        repository=repo,
        idempotency=idempotency,
        lifecycle=lifecycle,
        limits=mocker.MagicMock(),
    )

    payload = FlowRunCreate(flow_version_id=flow_version_id, session_id=session_id)

    with pytest.raises(ResourceBlockedServiceException, match="flow_not_active"):
        await service.create_flow_run(
            tenant_id=tenant_id,
            endpoint="/core/v1/flow-runs",
            idempotency_key="no-active",
            payload=payload,
        )
