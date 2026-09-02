"""Durable resume turns and the stranded-run reconciler (gap register §2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from temporalio.client import WorkflowExecutionStatus
from temporalio.service import RPCError, RPCStatusCode

from adapters.temporal.dtos import workflow_id_for
from adapters.temporal.engine import TemporalWorkflowEngine
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.schemas.workflow_dispatch import (
    FlowRunDispatchRequest,
    FlowRunOutcome,
)
from domain.execution.services.flow_run_reconciler import FlowRunReconciler
from domain.execution.services.state_machine import RunStatus
from exceptions.service_exceptions import DomainValidationException

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
    )
    defaults.update(kw)
    return FlowRunDispatchRequest(**defaults)


def _engine_with_client(client: MagicMock) -> TemporalWorkflowEngine:
    engine = TemporalWorkflowEngine()
    engine._client = client
    return engine


class TestResumeTurnWorkflowIdentity:
    def test_turn_zero_keeps_the_original_workflow_id(self) -> None:
        assert workflow_id_for(str(FLOW_RUN_ID)) == f"flow-run-{FLOW_RUN_ID}"
        assert workflow_id_for(str(FLOW_RUN_ID), 0) == f"flow-run-{FLOW_RUN_ID}"

    def test_resume_turns_get_distinct_workflow_ids(self) -> None:
        first = workflow_id_for(str(FLOW_RUN_ID), 1)
        second = workflow_id_for(str(FLOW_RUN_ID), 2)

        assert first == f"flow-run-{FLOW_RUN_ID}-t1"
        assert first != second

    @pytest.mark.asyncio
    async def test_start_resume_turn_starts_a_new_workflow_at_the_resume_node(self) -> None:
        client = MagicMock()
        handle = MagicMock()
        handle.first_execution_run_id = "run-turn-1"
        client.start_workflow = AsyncMock(return_value=handle)
        engine = _engine_with_client(client)

        dispatch = await engine.start_resume_turn(
            request=_request(turn_index=1, start_node_id="node-resume")
        )

        assert dispatch.workflow_id == f"flow-run-{FLOW_RUN_ID}-t1"
        payload = client.start_workflow.await_args.args[1]
        assert payload.start_node_id == "node-resume"
        assert payload.turn_index == 1

    @pytest.mark.asyncio
    async def test_start_resume_turn_requires_a_turn_index(self) -> None:
        engine = _engine_with_client(MagicMock())

        with pytest.raises(DomainValidationException, match="resume_turn_index_required"):
            await engine.start_resume_turn(request=_request(turn_index=0))


class TestDescribeFlowRun:
    @pytest.mark.asyncio
    async def test_missing_workflow_reports_none(self) -> None:
        client = MagicMock()
        handle = MagicMock()
        handle.describe = AsyncMock(side_effect=RPCError("not found", RPCStatusCode.NOT_FOUND, b""))
        client.get_workflow_handle = MagicMock(return_value=handle)
        engine = _engine_with_client(client)

        assert await engine.describe_flow_run(flow_run_id=FLOW_RUN_ID) is None

    @pytest.mark.asyncio
    async def test_running_workflow_reports_no_outcome(self) -> None:
        client = MagicMock()
        handle = MagicMock()
        handle.describe = AsyncMock(
            return_value=MagicMock(run_id="r", status=WorkflowExecutionStatus.RUNNING)
        )
        client.get_workflow_handle = MagicMock(return_value=handle)
        engine = _engine_with_client(client)

        status = await engine.describe_flow_run(flow_run_id=FLOW_RUN_ID)

        assert status is not None
        assert status.outcome is None

    @pytest.mark.asyncio
    async def test_terminated_workflow_maps_to_cancelled(self) -> None:
        client = MagicMock()
        handle = MagicMock()
        handle.describe = AsyncMock(
            return_value=MagicMock(run_id="r", status=WorkflowExecutionStatus.TERMINATED)
        )
        client.get_workflow_handle = MagicMock(return_value=handle)
        engine = _engine_with_client(client)

        status = await engine.describe_flow_run(flow_run_id=FLOW_RUN_ID)

        assert status is not None
        assert status.outcome is FlowRunOutcome.CANCELLED

    @pytest.mark.asyncio
    async def test_explicit_workflow_id_is_used_for_resume_turns(self) -> None:
        client = MagicMock()
        handle = MagicMock()
        handle.describe = AsyncMock(
            return_value=MagicMock(run_id="r", status=WorkflowExecutionStatus.RUNNING)
        )
        client.get_workflow_handle = MagicMock(return_value=handle)
        engine = _engine_with_client(client)

        await engine.describe_flow_run(
            flow_run_id=FLOW_RUN_ID, workflow_id=f"flow-run-{FLOW_RUN_ID}-t3"
        )

        client.get_workflow_handle.assert_called_once_with(f"flow-run-{FLOW_RUN_ID}-t3")


def _stale_flow_run(**kw) -> SimpleNamespace:
    defaults = dict(
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        status=RunStatus.RUNNING,
        temporal_workflow_id=None,
        updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _repository(stale: list[SimpleNamespace]) -> MagicMock:
    repository = MagicMock()
    repository.list_stale_running_flow_runs = AsyncMock(return_value=stale)
    repository.fail_flow_run = AsyncMock()
    repository.append_execution_event = AsyncMock()
    repository.get_flow_context = AsyncMock(return_value=(uuid4(), TENANT_ID))
    return repository


class TestFlowRunReconciler:
    @pytest.mark.asyncio
    async def test_fails_runs_whose_workflow_is_gone(self) -> None:
        stale = _stale_flow_run()
        repository = _repository([stale])
        engine = MagicMock()
        engine.describe_flow_run = AsyncMock(return_value=None)
        reconciler = FlowRunReconciler(
            repository=repository,
            workflow_engine=engine,
            stale_after_seconds=900,
            batch_size=50,
        )

        assert await reconciler.reconcile_once() == 1

        repository.fail_flow_run.assert_awaited_once()
        assert (
            repository.fail_flow_run.await_args.kwargs["failure_reason"]
            is FlowFailureReason.STRUCTURAL_ERROR
        )
        repository.append_execution_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_leaves_runs_whose_workflow_is_alive(self) -> None:
        repository = _repository([_stale_flow_run()])
        engine = MagicMock()
        engine.describe_flow_run = AsyncMock(
            return_value=SimpleNamespace(outcome=None, workflow_id="w", run_id="r")
        )
        reconciler = FlowRunReconciler(
            repository=repository,
            workflow_engine=engine,
            stale_after_seconds=900,
            batch_size=50,
        )

        assert await reconciler.reconcile_once() == 0

        repository.fail_flow_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_engine_error_is_treated_as_still_running(self) -> None:
        repository = _repository([_stale_flow_run()])
        engine = MagicMock()
        engine.describe_flow_run = AsyncMock(side_effect=RuntimeError("temporal down"))
        reconciler = FlowRunReconciler(
            repository=repository,
            workflow_engine=engine,
            stale_after_seconds=900,
            batch_size=50,
        )

        assert await reconciler.reconcile_once() == 0

        repository.fail_flow_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_without_an_engine_stale_runs_are_failed(self) -> None:
        repository = _repository([_stale_flow_run()])
        reconciler = FlowRunReconciler(
            repository=repository,
            workflow_engine=None,
            stale_after_seconds=900,
            batch_size=50,
        )

        assert await reconciler.reconcile_once() == 1

    @pytest.mark.asyncio
    async def test_uses_the_recorded_workflow_id_of_the_latest_turn(self) -> None:
        stale = _stale_flow_run(temporal_workflow_id="flow-run-x-t4")
        repository = _repository([stale])
        engine = MagicMock()
        engine.describe_flow_run = AsyncMock(return_value=None)
        reconciler = FlowRunReconciler(
            repository=repository,
            workflow_engine=engine,
            stale_after_seconds=900,
            batch_size=50,
        )

        await reconciler.reconcile_once()

        assert engine.describe_flow_run.await_args.kwargs["workflow_id"] == "flow-run-x-t4"

    @pytest.mark.asyncio
    async def test_second_pass_is_idempotent_because_the_row_left_the_stale_set(self) -> None:
        repository = _repository([])
        reconciler = FlowRunReconciler(
            repository=repository,
            workflow_engine=None,
            stale_after_seconds=900,
            batch_size=50,
        )

        assert await reconciler.reconcile_once() == 0
        repository.fail_flow_run.assert_not_called()
