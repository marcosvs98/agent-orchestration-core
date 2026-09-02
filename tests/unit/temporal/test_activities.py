"""FlowRunActivities behaviour with the domain layer mocked.

The rule these tests exist to protect: anything the in-process executor treats
as a flow failure must be *returned* as status="ERROR", never raised. A raised
exception is retried by Temporal, so a TypeError from a broken node class would
otherwise retry forever and burn LLM quota.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from adapters.temporal.activities import FlowRunActivities
from adapters.temporal.dtos import (
    ExecuteNodeInput,
    FinalizeFlowRunInput,
    FlowRunWorkflowInput,
)
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan
from domain.execution.services.graph_runtime.node_step_runner import (
    NodeStepOutcome,
    NodeStepStatus,
)
from domain.execution.services.state_machine import FlowRunStatus, RunStatus

TENANT_ID = uuid4()
FLOW_ID = uuid4()
FLOW_RUN_ID = uuid4()
SESSION_ID = uuid4()
INTERACTION_ID = uuid4()
CORRELATION_ID = uuid4()
FLOW_VERSION_ID = uuid4()
SNAPSHOT_ID = uuid4()


class _FakeTracer:
    def __init__(self) -> None:
        self.flushed = 0

    def observe(self, **_):
        return contextlib.nullcontext()

    def flush(self) -> None:
        self.flushed += 1


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        start_node_id="n1",
        ordered_nodes=["n1", "n2"],
        adjacency_map={},
        terminal_nodes={"n2"},
        structural_hash="hash",
        nodes={"n1": {"type": "ToolResolver"}, "n2": {"type": "ResponseBuilder"}},
    )


def _flow_run_row() -> SimpleNamespace:
    return SimpleNamespace(
        flow_run_id=FLOW_RUN_ID,
        flow_version_id=FLOW_VERSION_ID,
        session_id=SESSION_ID,
        user_id="test-user",
        interaction_id=INTERACTION_ID,
        correlation_id=CORRELATION_ID,
        trace_id=None,
        input={"user_input": "hello"},
        flow_graph_snapshot_id=SNAPSHOT_ID,
    )


def _policy(**limits):
    definition = MagicMock()
    definition.model_dump.return_value = {
        "limits": {"max_loop_iterations": 5, **limits},
        "llm": {"max_retries": 4},
        "tools": {"max_retries": 6},
    }
    return SimpleNamespace(definition=definition)


def _activities(repository: MagicMock, tracer: _FakeTracer | None = None) -> FlowRunActivities:
    execution_service = MagicMock()
    execution_service.repository = repository
    execution_service.runtime.step_runner = MagicMock()
    execution_service.hook = None
    execution_service.plan_compiler = MagicMock()
    execution_service.plan_compiler.compile = MagicMock(return_value=_plan())
    execution_service.policy_resolver = MagicMock()
    execution_service.policy_resolver.resolve = AsyncMock(return_value=_policy())
    execution_service.cache_adapter = MagicMock()
    execution_service.cache_adapter.get = AsyncMock(return_value=_plan().model_dump(mode="json"))
    execution_service.cache_adapter.set = AsyncMock()
    execution_service.idempotency = MagicMock()
    execution_service.idempotency.set_result = AsyncMock()
    return FlowRunActivities(
        execution_service=execution_service,
        tracer=tracer or _FakeTracer(),
    )


def _repository() -> MagicMock:
    repo = MagicMock()
    repo.get_flow_run = AsyncMock(return_value=_flow_run_row())
    repo.get_flow_graph_snapshot = AsyncMock(
        return_value=SimpleNamespace(
            graph_hash="hash", snapshot={}, flow_graph_snapshot_id=SNAPSHOT_ID
        )
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=None)
    repo.get_graph_state = AsyncMock(return_value=None)
    repo.upsert_graph_state = AsyncMock()
    repo.set_flow_run_status = AsyncMock()
    repo.set_flow_run_output = AsyncMock()
    repo.complete_flow_run = AsyncMock()
    repo.fail_flow_run = AsyncMock()
    repo.set_current_interaction_result_for_flow_run = AsyncMock()
    repo.append_execution_event = AsyncMock()
    repo.get_node_run = AsyncMock(return_value=None)
    return repo


def _workflow_input() -> FlowRunWorkflowInput:
    return FlowRunWorkflowInput(
        flow_run_id=str(FLOW_RUN_ID),
        tenant_id=str(TENANT_ID),
        session_id=str(SESSION_ID),
        user_id="test-user",
        flow_id=str(FLOW_ID),
        flow_version_id=str(FLOW_VERSION_ID),
        interaction_id=str(INTERACTION_ID),
        correlation_id=str(CORRELATION_ID),
        idempotency_key="key-1",
    )


def _execute_node_input(**kw) -> ExecuteNodeInput:
    defaults = dict(
        flow_run_id=str(FLOW_RUN_ID),
        tenant_id=str(TENANT_ID),
        flow_id=str(FLOW_ID),
        node_id="n1",
        step_index=0,
        loop_limit=5,
    )
    defaults.update(kw)
    return ExecuteNodeInput(**defaults)


@pytest.mark.asyncio
async def test_prepare_seeds_graph_state_and_marks_the_run_running() -> None:
    repo = _repository()
    acts = _activities(repo)

    summary = await ActivityEnvironment().run(acts.prepare_flow_run, _workflow_input())

    assert summary.start_node_id == "n1"
    assert summary.loop_limit == 5
    assert summary.llm_max_retries == 4
    assert summary.tools_max_retries == 6
    repo.upsert_graph_state.assert_awaited_once()
    seeded = repo.upsert_graph_state.await_args.kwargs["state"]
    assert seeded["current_node_id"] == "n1"
    assert seeded["metadata"]["runtime_policy"]["limits"]["max_loop_iterations"] == 5
    repo.set_flow_run_status.assert_awaited_once_with(
        flow_run_id=FLOW_RUN_ID,
        status=RunStatus.RUNNING,
        canonical_status=FlowRunStatus.RUNNING,
    )


@pytest.mark.asyncio
async def test_prepare_maps_policy_durations_onto_the_summary() -> None:
    repo = _repository()
    acts = _activities(repo)
    acts.policy_resolver.resolve = AsyncMock(
        return_value=_policy(max_node_duration_ms=1234, max_total_duration_ms=99_000)
    )

    summary = await ActivityEnvironment().run(acts.prepare_flow_run, _workflow_input())

    assert summary.max_node_duration_ms == 1234
    assert summary.max_total_duration_ms == 99_000


@pytest.mark.asyncio
async def test_prepare_does_not_reseed_an_existing_graph_state() -> None:
    repo = _repository()
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "n2"}))
    acts = _activities(repo)

    await ActivityEnvironment().run(acts.prepare_flow_run, _workflow_input())

    repo.upsert_graph_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_raises_non_retryable_when_the_run_is_missing() -> None:
    repo = _repository()
    repo.get_flow_run = AsyncMock(return_value=None)
    acts = _activities(repo)

    with pytest.raises(ApplicationError) as exc:
        await ActivityEnvironment().run(acts.prepare_flow_run, _workflow_input())

    assert exc.value.non_retryable is True


def _graph_state() -> SimpleNamespace:
    return SimpleNamespace(
        state={
            "current_node_id": "n1",
            "state": {"k": "v"},
            "memory": [],
            "metadata": {"runtime_policy": {"limits": {}}},
        }
    )


@pytest.mark.asyncio
async def test_execute_node_advance_reports_the_next_node() -> None:
    repo = _repository()
    repo.get_graph_state = AsyncMock(return_value=_graph_state())
    acts = _activities(repo)
    node_run_id = uuid4()
    acts.step_runner.run_step = AsyncMock(
        return_value=NodeStepOutcome(
            status=NodeStepStatus.ADVANCE,
            node_type="ToolResolver",
            node_run_id=node_run_id,
            next_node_id="n2",
            loop_edge_keys=["n1->n2"],
        )
    )

    out = await ActivityEnvironment().run(acts.execute_node, _execute_node_input())

    assert out.status == "SUCCESS"
    assert out.next_node_id == "n2"
    assert out.terminal is False
    assert out.node_run_id == str(node_run_id)
    assert out.loop_edge_keys == ["n1->n2"]


@pytest.mark.asyncio
async def test_execute_node_reconstitutes_context_from_graph_state() -> None:
    repo = _repository()
    repo.get_graph_state = AsyncMock(return_value=_graph_state())
    acts = _activities(repo)
    acts.step_runner.run_step = AsyncMock(
        return_value=NodeStepOutcome(status=NodeStepStatus.TERMINAL, node_type="ResponseBuilder")
    )

    await ActivityEnvironment().run(acts.execute_node, _execute_node_input(node_id="n2"))

    context = acts.step_runner.run_step.await_args.kwargs["context"]
    assert context.current_node_id == "n2"
    assert context.tenant_id == TENANT_ID
    assert context.flow_id == FLOW_ID
    assert context.flow_run_id == FLOW_RUN_ID
    assert context.state == {"k": "v"}
    assert context.on_content_delta is None


@pytest.mark.asyncio
async def test_execute_node_returns_error_instead_of_raising_on_flow_failure() -> None:
    repo = _repository()
    repo.get_graph_state = AsyncMock(return_value=_graph_state())
    acts = _activities(repo)
    acts.step_runner.run_step = AsyncMock(
        return_value=NodeStepOutcome(
            status=NodeStepStatus.FAILED,
            node_type="IntentClassifier",
            failure_reason=FlowFailureReason.STRUCTURAL_ERROR,
            failure_exception=TypeError("object.__init__() takes exactly one argument"),
        )
    )

    out = await ActivityEnvironment().run(acts.execute_node, _execute_node_input())

    assert out.status == "ERROR"
    assert out.failure_reason == "STRUCTURAL_ERROR"


@pytest.mark.asyncio
async def test_execute_node_reports_needs_input_with_resume_node() -> None:
    repo = _repository()
    repo.get_graph_state = AsyncMock(return_value=_graph_state())
    acts = _activities(repo)
    acts.step_runner.run_step = AsyncMock(
        return_value=NodeStepOutcome(
            status=NodeStepStatus.NEEDS_INPUT,
            node_type="QueryClarifier",
            resume_to_node_id="n1",
        )
    )

    out = await ActivityEnvironment().run(acts.execute_node, _execute_node_input())

    assert out.status == "NEEDS_INPUT"
    assert out.resume_to_node_id == "n1"


@pytest.mark.asyncio
async def test_execute_node_raises_non_retryable_without_graph_state() -> None:
    repo = _repository()
    repo.get_graph_state = AsyncMock(return_value=None)
    acts = _activities(repo)

    with pytest.raises(ApplicationError) as exc:
        await ActivityEnvironment().run(acts.execute_node, _execute_node_input())

    assert exc.value.non_retryable is True


@pytest.mark.asyncio
async def test_finalize_completed_writes_output_and_releases_idempotency() -> None:
    repo = _repository()
    node_run_id = uuid4()
    repo.get_node_run = AsyncMock(return_value=SimpleNamespace(output={"data": {"text": "done"}}))
    repo.get_graph_state = AsyncMock(return_value=_graph_state())
    tracer = _FakeTracer()
    acts = _activities(repo, tracer)

    await ActivityEnvironment().run(
        acts.finalize_flow_run,
        FinalizeFlowRunInput(
            flow_run_id=str(FLOW_RUN_ID),
            tenant_id=str(TENANT_ID),
            session_id=str(SESSION_ID),
            user_id="test-user",
            correlation_id=str(CORRELATION_ID),
            outcome="COMPLETED",
            last_node_id="n2",
            last_node_run_id=str(node_run_id),
            idempotency_key="key-1",
        ),
    )

    repo.complete_flow_run.assert_awaited_once()
    assert repo.complete_flow_run.await_args.kwargs["output"] == {"text": "done"}
    acts.idempotency.set_result.assert_awaited_once()
    assert tracer.flushed == 1


@pytest.mark.asyncio
async def test_finalize_waiting_parks_the_run() -> None:
    repo = _repository()
    acts = _activities(repo)

    await ActivityEnvironment().run(
        acts.finalize_flow_run,
        FinalizeFlowRunInput(
            flow_run_id=str(FLOW_RUN_ID),
            tenant_id=str(TENANT_ID),
            session_id=str(SESSION_ID),
            user_id="test-user",
            correlation_id=str(CORRELATION_ID),
            outcome="WAITING",
        ),
    )

    repo.set_flow_run_status.assert_awaited_once_with(
        flow_run_id=FLOW_RUN_ID,
        status=RunStatus.WAITING_INPUT,
        canonical_status=FlowRunStatus.WAITING,
    )


@pytest.mark.asyncio
async def test_finalize_failed_records_the_reason() -> None:
    repo = _repository()
    acts = _activities(repo)

    await ActivityEnvironment().run(
        acts.finalize_flow_run,
        FinalizeFlowRunInput(
            flow_run_id=str(FLOW_RUN_ID),
            tenant_id=str(TENANT_ID),
            session_id=str(SESSION_ID),
            user_id="test-user",
            correlation_id=str(CORRELATION_ID),
            outcome="FAILED",
            failure_reason="NO_MATCHING_EDGE",
        ),
    )

    repo.fail_flow_run.assert_awaited_once()
    assert (
        repo.fail_flow_run.await_args.kwargs["failure_reason"] == FlowFailureReason.NO_MATCHING_EDGE
    )
    repo.append_execution_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_cancelled_uses_the_cancelled_run_status() -> None:
    repo = _repository()
    acts = _activities(repo)

    await ActivityEnvironment().run(
        acts.finalize_flow_run,
        FinalizeFlowRunInput(
            flow_run_id=str(FLOW_RUN_ID),
            tenant_id=str(TENANT_ID),
            session_id=str(SESSION_ID),
            user_id="test-user",
            correlation_id=str(CORRELATION_ID),
            outcome="CANCELLED",
        ),
    )

    repo.set_flow_run_status.assert_awaited_once_with(
        flow_run_id=FLOW_RUN_ID,
        status=RunStatus.CANCELLED,
        canonical_status=FlowRunStatus.FAILED,
    )


@pytest.mark.asyncio
async def test_finalize_unknown_failure_reason_falls_back_to_structural_error() -> None:
    repo = _repository()
    acts = _activities(repo)

    await ActivityEnvironment().run(
        acts.finalize_flow_run,
        FinalizeFlowRunInput(
            flow_run_id=str(FLOW_RUN_ID),
            tenant_id=str(TENANT_ID),
            session_id=str(SESSION_ID),
            user_id="test-user",
            correlation_id=str(CORRELATION_ID),
            outcome="FAILED",
            failure_reason="not-a-real-reason",
        ),
    )

    assert (
        repo.fail_flow_run.await_args.kwargs["failure_reason"] == FlowFailureReason.STRUCTURAL_ERROR
    )


@pytest.mark.asyncio
async def test_plan_is_compiled_and_cached_on_cache_miss() -> None:
    repo = _repository()
    acts = _activities(repo)
    acts.cache_adapter.get = AsyncMock(return_value=None)

    await ActivityEnvironment().run(acts.prepare_flow_run, _workflow_input())

    acts.plan_compiler.compile.assert_called_once()
    acts.cache_adapter.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_graph_snapshot_is_non_retryable() -> None:
    repo = _repository()
    repo.get_flow_graph_snapshot = AsyncMock(return_value=None)
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=None)
    acts = _activities(repo)

    with pytest.raises(ApplicationError) as exc:
        await ActivityEnvironment().run(acts.prepare_flow_run, _workflow_input())

    assert exc.value.non_retryable is True


class _StubNodeRun:
    def __init__(self, output: dict | None) -> None:
        self.output = output


class _StubNodeRunRepository:
    def __init__(self, node_run: object | None) -> None:
        self._node_run = node_run

    async def get_node_run(self, _node_run_id):
        return self._node_run


def _activities_with(node_run: object | None):
    from adapters.temporal.activities import FlowRunActivities

    activities = FlowRunActivities.__new__(FlowRunActivities)
    activities.repository = _StubNodeRunRepository(node_run)
    return activities


@pytest.mark.asyncio
async def test_last_node_output_reads_the_node_run_output_column() -> None:
    activities = _activities_with(_StubNodeRun({"data": {"status": "success"}}))

    assert await activities._last_node_output(str(uuid4())) == {"status": "success"}


@pytest.mark.asyncio
async def test_last_node_output_is_empty_without_a_node_run_id() -> None:
    assert await _activities_with(None)._last_node_output(None) == {}


@pytest.mark.asyncio
async def test_last_node_output_is_empty_when_the_node_run_is_missing() -> None:
    assert await _activities_with(None)._last_node_output(str(uuid4())) == {}


@pytest.mark.asyncio
async def test_last_node_output_is_empty_when_data_is_not_a_mapping() -> None:
    activities = _activities_with(_StubNodeRun({"data": ["not", "a", "dict"]}))

    assert await activities._last_node_output(str(uuid4())) == {}


@pytest.mark.asyncio
async def test_last_node_output_tolerates_an_empty_output_column() -> None:
    activities = _activities_with(_StubNodeRun(None))

    assert await activities._last_node_output(str(uuid4())) == {}
