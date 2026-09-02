"""TemporalWorkflowEngine dispatch behaviour with the Temporal client mocked."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from temporalio.common import WorkflowIDReusePolicy

from adapters.temporal.dtos import FlowRunWorkflowResult
from adapters.temporal.engine import TemporalWorkflowEngine
from domain.execution.schemas.workflow_dispatch import (
    FlowRunDispatch,
    FlowRunDispatchRequest,
    FlowRunOutcome,
)

FLOW_RUN_ID = uuid4()
TENANT_ID = uuid4()


def _request(**kw) -> FlowRunDispatchRequest:
    defaults = dict(
        flow_run_id=FLOW_RUN_ID,
        tenant_id=TENANT_ID,
        session_id=uuid4(),
        user_id="test-user",
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        interaction_id=uuid4(),
        correlation_id=uuid4(),
        idempotency_key="key-1",
    )
    defaults.update(kw)
    return FlowRunDispatchRequest(**defaults)


def _engine_with_client(client: MagicMock) -> TemporalWorkflowEngine:
    engine = TemporalWorkflowEngine()
    engine._client = client
    return engine


@pytest.mark.asyncio
async def test_start_flow_run_uses_a_deterministic_workflow_id() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.first_execution_run_id = "run-abc"
    client.start_workflow = AsyncMock(return_value=handle)
    engine = _engine_with_client(client)

    dispatch = await engine.start_flow_run(request=_request())

    assert dispatch.workflow_id == f"flow-run-{FLOW_RUN_ID}"
    assert dispatch.run_id == "run-abc"
    kwargs = client.start_workflow.await_args.kwargs
    assert kwargs["id"] == f"flow-run-{FLOW_RUN_ID}"
    assert kwargs["id_reuse_policy"] == WorkflowIDReusePolicy.REJECT_DUPLICATE


@pytest.mark.asyncio
async def test_start_flow_run_passes_identifiers_not_payloads() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.first_execution_run_id = "run-abc"
    client.start_workflow = AsyncMock(return_value=handle)
    engine = _engine_with_client(client)
    request = _request(start_node_id="n7")

    await engine.start_flow_run(request=request)

    payload = client.start_workflow.await_args.args[1]
    assert payload.flow_run_id == str(FLOW_RUN_ID)
    assert payload.start_node_id == "n7"
    assert payload.idempotency_key == "key-1"


@pytest.mark.asyncio
async def test_start_flow_run_omits_priority_when_fairness_is_off() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.first_execution_run_id = "r"
    client.start_workflow = AsyncMock(return_value=handle)
    engine = _engine_with_client(client)

    with patch("adapters.temporal.engine.settings") as mock_settings:
        mock_settings.TEMPORAL_FAIRNESS_ENABLED = False
        mock_settings.TEMPORAL_TASK_QUEUE = "flow-runs"
        mock_settings.TEMPORAL_WORKFLOW_RUN_TIMEOUT_MS = 60_000
        await engine.start_flow_run(request=_request())

    assert client.start_workflow.await_args.kwargs["priority"] is None


@pytest.mark.asyncio
async def test_start_flow_run_sets_tenant_fairness_key_when_enabled() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.first_execution_run_id = "r"
    client.start_workflow = AsyncMock(return_value=handle)
    engine = _engine_with_client(client)

    with patch("adapters.temporal.engine.settings") as mock_settings:
        mock_settings.TEMPORAL_FAIRNESS_ENABLED = True
        mock_settings.TEMPORAL_TASK_QUEUE = "flow-runs"
        mock_settings.TEMPORAL_WORKFLOW_RUN_TIMEOUT_MS = 60_000
        await engine.start_flow_run(request=_request())

    priority = client.start_workflow.await_args.kwargs["priority"]
    assert priority.fairness_key == str(TENANT_ID)


@pytest.mark.asyncio
async def test_await_turn_returns_the_workflow_outcome() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.result = AsyncMock(
        return_value=FlowRunWorkflowResult(
            flow_run_id=str(FLOW_RUN_ID),
            outcome="COMPLETED",
            steps_executed=3,
        )
    )
    client.get_workflow_handle_for = MagicMock(return_value=handle)
    engine = _engine_with_client(client)

    status = await engine.await_flow_run_turn(
        dispatch=FlowRunDispatch(flow_run_id=FLOW_RUN_ID, workflow_id="wf", run_id="run"),
        timeout_ms=5_000,
    )

    assert status.outcome == FlowRunOutcome.COMPLETED
    assert status.steps_executed == 3


@pytest.mark.asyncio
async def test_await_turn_returns_without_outcome_on_timeout() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.result = AsyncMock(side_effect=asyncio.TimeoutError())
    client.get_workflow_handle_for = MagicMock(return_value=handle)
    engine = _engine_with_client(client)

    status = await engine.await_flow_run_turn(
        dispatch=FlowRunDispatch(flow_run_id=FLOW_RUN_ID, workflow_id="wf", run_id="run"),
        timeout_ms=10,
    )

    assert status.outcome is None
    assert status.workflow_id == "wf"


@pytest.mark.asyncio
async def test_cancel_targets_the_derived_workflow_id() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.cancel = AsyncMock()
    client.get_workflow_handle = MagicMock(return_value=handle)
    engine = _engine_with_client(client)

    await engine.cancel_flow_run(flow_run_id=FLOW_RUN_ID, reason="operator")

    client.get_workflow_handle.assert_called_once_with(f"flow-run-{FLOW_RUN_ID}")
    handle.cancel.assert_awaited_once()


@pytest.mark.asyncio
async def test_describe_reports_the_current_run_id() -> None:
    client = MagicMock()
    handle = MagicMock()
    handle.describe = AsyncMock(return_value=MagicMock(run_id="run-9"))
    client.get_workflow_handle = MagicMock(return_value=handle)
    engine = _engine_with_client(client)

    status = await engine.describe_flow_run(flow_run_id=FLOW_RUN_ID)

    assert status.run_id == "run-9"
    assert status.workflow_id == f"flow-run-{FLOW_RUN_ID}"


@pytest.mark.asyncio
async def test_client_is_connected_once_and_reused() -> None:
    engine = TemporalWorkflowEngine()
    built = MagicMock()

    with patch(
        "adapters.temporal.engine.build_temporal_client", AsyncMock(return_value=built)
    ) as connect:
        first, second = await asyncio.gather(engine.client(), engine.client())

    assert first is built
    assert second is built
    connect.assert_awaited_once()
