import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.observability.hooks import DbExecutionEventHook


class TestDbExecutionEventHook:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=ExecutionRepository)
        repo.append_execution_event = AsyncMock()
        return repo

    @pytest.fixture
    def tracer(self):
        t = MagicMock()
        t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
        return t

    @pytest.fixture
    def hook(self, repository, tracer):
        return DbExecutionEventHook(repository, tracer)

    @pytest.mark.asyncio
    async def test_on_flow_start_calls_repository_with_correct_data(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        payload = {"interaction_id": str(uuid4()), "channel": "http"}

        await hook.on_flow_start(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            payload=payload,
        )

        repository.append_execution_event.assert_called_once()
        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["tenant_id"] == tenant_id
        assert call_kwargs["session_id"] == session_id
        assert call_kwargs["flow_run_id"] == flow_run_id
        assert call_kwargs["correlation_id"] == correlation_id
        assert call_kwargs["payload"] == payload
        assert call_kwargs["event_type"] == ExecutionEventType.FlowStarted.value
        assert call_kwargs["node_id"] is None
        assert call_kwargs["edge_id"] is None
        assert call_kwargs["schema_version"] == 1

    @pytest.mark.asyncio
    async def test_on_node_start_calls_repository_with_node_id(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        node_id = uuid4()
        payload = {"node_id": str(node_id)}

        await hook.on_node_start(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            node_id=node_id,
            payload=payload,
        )

        repository.append_execution_event.assert_called_once()
        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["node_id"] == node_id
        assert call_kwargs["event_type"] == ExecutionEventType.NodeStarted.value

    @pytest.mark.asyncio
    async def test_on_node_complete_calls_repository_with_payload(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        node_id = uuid4()
        payload = {"status": "SUCCESS", "output": "result"}

        await hook.on_node_complete(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            node_id=node_id,
            payload=payload,
        )

        repository.append_execution_event.assert_called_once()
        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["payload"] == payload
        assert call_kwargs["event_type"] == ExecutionEventType.NodeCompleted.value
        assert call_kwargs["node_id"] == node_id

    @pytest.mark.asyncio
    async def test_on_edge_evaluated_calls_repository_with_edge_id(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        node_id = uuid4()
        edge_id = "node1->node2"
        payload = {"from_node": "node1", "to_node": "node2", "result": True}

        await hook.on_edge_evaluated(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            node_id=node_id,
            edge_id=edge_id,
            payload=payload,
        )

        repository.append_execution_event.assert_called_once()
        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["edge_id"] == edge_id
        assert call_kwargs["node_id"] == node_id
        assert call_kwargs["event_type"] == ExecutionEventType.EdgeEvaluated.value

    @pytest.mark.asyncio
    async def test_on_flow_complete_calls_repository_with_payload(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        payload = {"terminated_at": "node_final", "payload": "result"}

        await hook.on_flow_complete(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            payload=payload,
        )

        repository.append_execution_event.assert_called_once()
        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["payload"] == payload
        assert call_kwargs["event_type"] == ExecutionEventType.FlowCompleted.value
        assert call_kwargs["node_id"] is None
        assert call_kwargs["edge_id"] is None

    @pytest.mark.asyncio
    async def test_on_flow_failed_calls_repository_with_reason(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        payload = {"reason": "NODE_NOT_FOUND"}

        await hook.on_flow_failed(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            payload=payload,
        )

        repository.append_execution_event.assert_called_once()
        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["payload"] == payload
        assert call_kwargs["event_type"] == ExecutionEventType.FlowFailed.value

    @pytest.mark.asyncio
    async def test_safe_emit_swallows_exceptions(self, hook, repository):
        repository.append_execution_event = AsyncMock(side_effect=Exception("Database error"))
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()

        await hook.on_flow_start(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            payload={},
        )

        repository.append_execution_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_flow_start_with_causation_id(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        causation_id = uuid4()
        payload = {}

        await hook.on_flow_start(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            payload=payload,
            causation_id=causation_id,
        )

        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["causation_id"] == causation_id

    @pytest.mark.asyncio
    async def test_on_flow_start_with_custom_schema_version(self, hook, repository):
        tenant_id = uuid4()
        session_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()
        payload = {}

        await hook.on_flow_start(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            payload=payload,
            schema_version=2,
        )

        call_kwargs = repository.append_execution_event.call_args.kwargs
        assert call_kwargs["schema_version"] == 2
