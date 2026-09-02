"""FlowRunWorkflow traversal behaviour with all activities mocked.

The workflow is a generic graph interpreter: it never sees node payloads, only
control signals. These tests script those signals and assert the traversal,
loop accounting, terminal detection and finalize call.
"""

from __future__ import annotations

import uuid

import pytest
from temporalio import activity
from temporalio.worker import Worker

from adapters.temporal.dtos import (
    ExecuteNodeInput,
    ExecuteNodeOutput,
    FinalizeFlowRunInput,
    FlowRunPlanSummary,
    FlowRunWorkflowInput,
)
from adapters.temporal.sandbox import build_workflow_runner
from adapters.temporal.workflow import FlowRunWorkflow


def _summary(*, max_steps: int = 20, loop_limit: int = 3) -> FlowRunPlanSummary:
    return FlowRunPlanSummary(
        start_node_id="n1",
        max_steps=max_steps,
        loop_limit=loop_limit,
        node_count=3,
        max_node_duration_ms=5_000,
        max_total_duration_ms=60_000,
        llm_max_retries=2,
        tools_max_retries=2,
    )


class _Harness:
    def __init__(self, steps: dict[str, ExecuteNodeOutput], summary: FlowRunPlanSummary):
        self.steps = steps
        self.summary = summary
        self.finalized: list[FinalizeFlowRunInput] = []
        self.executed: list[str] = []
        self.attempts: dict[str, int] = {}

    def activities(self) -> list:
        harness = self

        @activity.defn(name="prepare_flow_run")
        async def prepare_flow_run(_: FlowRunWorkflowInput) -> FlowRunPlanSummary:
            return harness.summary

        @activity.defn(name="execute_node")
        async def execute_node(payload: ExecuteNodeInput) -> ExecuteNodeOutput:
            harness.executed.append(payload.node_id)
            harness.attempts[payload.node_id] = harness.attempts.get(payload.node_id, 0) + 1
            return harness.steps[payload.node_id]

        @activity.defn(name="finalize_flow_run")
        async def finalize_flow_run(payload: FinalizeFlowRunInput) -> None:
            harness.finalized.append(payload)

        return [prepare_flow_run, execute_node, finalize_flow_run]


def _advance(node_type: str, next_node_id: str, **kw) -> ExecuteNodeOutput:
    return ExecuteNodeOutput(
        node_type=node_type,
        node_run_id=str(uuid.uuid4()),
        status="SUCCESS",
        next_node_id=next_node_id,
        **kw,
    )


def _terminal(node_type: str = "ResponseBuilder") -> ExecuteNodeOutput:
    return ExecuteNodeOutput(
        node_type=node_type,
        node_run_id=str(uuid.uuid4()),
        status="SUCCESS",
        terminal=True,
    )


async def _run(env, task_queue, workflow_input, harness: _Harness):
    async with Worker(
        env.client,
        task_queue=task_queue,
        workflow_runner=build_workflow_runner(),
        workflows=[FlowRunWorkflow],
        activities=harness.activities(),
    ):
        return await env.client.execute_workflow(
            FlowRunWorkflow.run,
            workflow_input,
            id=str(uuid.uuid4()),
            task_queue=task_queue,
        )


@pytest.mark.asyncio
async def test_linear_graph_completes(workflow_env, task_queue, workflow_input):
    harness = _Harness(
        {
            "n1": _advance("IntentClassifier", "n2"),
            "n2": _advance("ToolExecutor", "n3"),
            "n3": _terminal(),
        },
        _summary(),
    )

    result = await _run(workflow_env, task_queue, workflow_input, harness)

    assert result.outcome == "COMPLETED"
    assert result.steps_executed == 3
    assert harness.executed == ["n1", "n2", "n3"]
    assert [f.outcome for f in harness.finalized] == ["COMPLETED"]
    assert harness.finalized[0].last_node_id == "n3"


@pytest.mark.asyncio
async def test_terminal_on_first_node_short_circuits(workflow_env, task_queue, workflow_input):
    harness = _Harness({"n1": _terminal("HumanFallback")}, _summary())

    result = await _run(workflow_env, task_queue, workflow_input, harness)

    assert result.outcome == "COMPLETED"
    assert result.steps_executed == 1
    assert harness.executed == ["n1"]


@pytest.mark.asyncio
async def test_needs_input_parks_the_run_as_waiting(workflow_env, task_queue, workflow_input):
    harness = _Harness(
        {
            "n1": _advance("IntentClassifier", "n2"),
            "n2": ExecuteNodeOutput(
                node_type="QueryClarifier",
                node_run_id=str(uuid.uuid4()),
                status="NEEDS_INPUT",
                resume_to_node_id="n1",
            ),
        },
        _summary(),
    )

    result = await _run(workflow_env, task_queue, workflow_input, harness)

    assert result.outcome == "WAITING"
    assert harness.finalized[0].outcome == "WAITING"
    assert harness.finalized[0].last_node_id == "n2"


@pytest.mark.asyncio
async def test_node_error_fails_the_run_with_its_reason(workflow_env, task_queue, workflow_input):
    harness = _Harness(
        {
            "n1": ExecuteNodeOutput(
                node_type="ToolResolver",
                node_run_id=str(uuid.uuid4()),
                status="ERROR",
                failure_reason="NO_MATCHING_EDGE",
            )
        },
        _summary(),
    )

    result = await _run(workflow_env, task_queue, workflow_input, harness)

    assert result.outcome == "FAILED"
    assert result.failure_reason == "NO_MATCHING_EDGE"
    assert harness.finalized[0].failure_reason == "NO_MATCHING_EDGE"


@pytest.mark.asyncio
async def test_loop_limit_is_enforced_from_workflow_state(workflow_env, task_queue, workflow_input):
    harness = _Harness(
        {"n1": _advance("ToolResolver", "n1", loop_edge_keys=["n1->n1"])},
        _summary(max_steps=50, loop_limit=3),
    )

    result = await _run(workflow_env, task_queue, workflow_input, harness)

    assert result.outcome == "FAILED"
    assert result.failure_reason == "EDGE_EVALUATION_ERROR"
    assert len(harness.executed) == 4


@pytest.mark.asyncio
async def test_max_steps_exhaustion_fails_the_run(workflow_env, task_queue, workflow_input):
    harness = _Harness(
        {"n1": _advance("ToolResolver", "n1")},
        _summary(max_steps=5, loop_limit=100),
    )

    result = await _run(workflow_env, task_queue, workflow_input, harness)

    assert result.outcome == "FAILED"
    assert result.failure_reason == "MAX_STEPS_EXCEEDED"
    assert result.steps_executed == 5


@pytest.mark.asyncio
async def test_transient_activity_failure_is_retried_then_succeeds(
    workflow_env, task_queue, workflow_input
):
    harness = _Harness({"n1": _terminal()}, _summary())
    calls = {"n": 0}

    @activity.defn(name="prepare_flow_run")
    async def prepare_flow_run(_: FlowRunWorkflowInput) -> FlowRunPlanSummary:
        return harness.summary

    @activity.defn(name="execute_node")
    async def flaky_execute_node(payload: ExecuteNodeInput) -> ExecuteNodeOutput:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("database temporarily unavailable")
        harness.executed.append(payload.node_id)
        return harness.steps[payload.node_id]

    @activity.defn(name="finalize_flow_run")
    async def finalize_flow_run(payload: FinalizeFlowRunInput) -> None:
        harness.finalized.append(payload)

    async with Worker(
        workflow_env.client,
        task_queue=task_queue,
        workflow_runner=build_workflow_runner(),
        workflows=[FlowRunWorkflow],
        activities=[prepare_flow_run, flaky_execute_node, finalize_flow_run],
    ):
        result = await workflow_env.client.execute_workflow(
            FlowRunWorkflow.run,
            workflow_input,
            id=str(uuid.uuid4()),
            task_queue=task_queue,
        )

    assert result.outcome == "COMPLETED"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_progress_query_reports_current_node(workflow_env, task_queue, workflow_input):
    harness = _Harness(
        {"n1": _advance("IntentClassifier", "n2"), "n2": _terminal()},
        _summary(),
    )

    async with Worker(
        workflow_env.client,
        task_queue=task_queue,
        workflow_runner=build_workflow_runner(),
        workflows=[FlowRunWorkflow],
        activities=harness.activities(),
    ):
        handle = await workflow_env.client.start_workflow(
            FlowRunWorkflow.run,
            workflow_input,
            id=str(uuid.uuid4()),
            task_queue=task_queue,
        )
        await handle.result()
        progress = await handle.query(FlowRunWorkflow.get_progress)

    assert progress.flow_run_id == workflow_input.flow_run_id
    assert progress.outcome == "COMPLETED"
    assert progress.step_index == 2
