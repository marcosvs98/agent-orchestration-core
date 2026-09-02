from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from adapters.temporal.activities import FlowRunActivities
    from adapters.temporal.dtos import (
        ExecuteNodeInput,
        ExecuteNodeOutput,
        FinalizeFlowRunInput,
        FlowRunPlanSummary,
        FlowRunProgress,
        FlowRunWorkflowInput,
        FlowRunWorkflowResult,
        OutcomeLiteral,
    )

NON_RETRYABLE_ERROR_TYPES = [
    "DomainValidationException",
    "NotFoundServiceException",
    "TypeError",
    "AttributeError",
]

PREPARE_TIMEOUT = timedelta(seconds=60)
FINALIZE_TIMEOUT = timedelta(seconds=60)


def _node_retry_policy(summary: FlowRunPlanSummary) -> RetryPolicy:
    return RetryPolicy(
        initial_interval=timedelta(milliseconds=200),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=10),
        maximum_attempts=summary.tools_max_retries + 1,
        non_retryable_error_types=NON_RETRYABLE_ERROR_TYPES,
    )


@workflow.defn
class FlowRunWorkflow:
    """Generic interpreter for any published flow graph.

    The traversal loop, step bound and loop counters live here so they survive
    a worker crash. Node execution and every database write happen in
    activities. This workflow is turn-scoped: it returns when the run reaches
    COMPLETED, FAILED or WAITING, mirroring where the in-process
    RuntimeExecutor returns today.
    """

    def __init__(self) -> None:
        self._flow_run_id: str = ""
        self._step_index: int = 0
        self._current_node_id: str | None = None
        self._outcome: OutcomeLiteral | None = None
        self._counters: dict[str, int] = {}

    @workflow.query
    def get_progress(self) -> FlowRunProgress:
        return FlowRunProgress(
            flow_run_id=self._flow_run_id,
            step_index=self._step_index,
            current_node_id=self._current_node_id,
            outcome=self._outcome,
        )

    @workflow.run
    async def run(self, payload: FlowRunWorkflowInput) -> FlowRunWorkflowResult:
        self._flow_run_id = payload.flow_run_id
        acts = FlowRunActivities

        try:
            summary: FlowRunPlanSummary = await workflow.execute_activity_method(
                acts.prepare_flow_run,
                payload,
                start_to_close_timeout=PREPARE_TIMEOUT,
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    non_retryable_error_types=NON_RETRYABLE_ERROR_TYPES,
                ),
            )
        except Exception:
            return await self._finalize(payload, "FAILED", "STRUCTURAL_ERROR", None, None)

        self._current_node_id = payload.start_node_id or summary.start_node_id
        node_timeout = timedelta(milliseconds=summary.max_node_duration_ms)
        retry_policy = _node_retry_policy(summary)

        for _ in range(summary.max_steps):
            step: ExecuteNodeOutput = await workflow.execute_activity_method(
                acts.execute_node,
                ExecuteNodeInput(
                    flow_run_id=payload.flow_run_id,
                    tenant_id=payload.tenant_id,
                    flow_id=payload.flow_id,
                    node_id=self._current_node_id,
                    step_index=self._step_index,
                    loop_limit=summary.loop_limit,
                    trace_id=payload.trace_id,
                    parent_observation_id=payload.root_observation_id,
                ),
                start_to_close_timeout=node_timeout,
                retry_policy=retry_policy,
            )
            self._step_index += 1
            executed_node_id = self._current_node_id

            for key in step.loop_edge_keys:
                self._counters[key] = self._counters.get(key, 0) + 1
                if self._counters[key] > summary.loop_limit:
                    return await self._finalize(
                        payload,
                        "FAILED",
                        "EDGE_EVALUATION_ERROR",
                        executed_node_id,
                        step.node_run_id,
                    )

            if step.status == "NEEDS_INPUT":
                return await self._finalize(
                    payload, "WAITING", None, executed_node_id, step.node_run_id
                )

            if step.terminal:
                return await self._finalize(
                    payload, "COMPLETED", None, executed_node_id, step.node_run_id
                )

            if step.status == "ERROR" or step.next_node_id is None:
                return await self._finalize(
                    payload,
                    "FAILED",
                    step.failure_reason or "STRUCTURAL_ERROR",
                    executed_node_id,
                    step.node_run_id,
                )

            self._current_node_id = step.next_node_id

        return await self._finalize(
            payload, "FAILED", "MAX_STEPS_EXCEEDED", self._current_node_id, None
        )

    async def _finalize(
        self,
        payload: FlowRunWorkflowInput,
        outcome: OutcomeLiteral,
        failure_reason: str | None,
        last_node_id: str | None,
        last_node_run_id: str | None,
    ) -> FlowRunWorkflowResult:
        self._outcome = outcome
        await workflow.execute_activity_method(
            FlowRunActivities.finalize_flow_run,
            FinalizeFlowRunInput(
                flow_run_id=payload.flow_run_id,
                tenant_id=payload.tenant_id,
                session_id=payload.session_id,
                user_id=payload.user_id,
                correlation_id=payload.correlation_id,
                outcome=outcome,
                failure_reason=failure_reason,
                last_node_id=last_node_id,
                last_node_run_id=last_node_run_id,
                idempotency_key=payload.idempotency_key,
            ),
            start_to_close_timeout=FINALIZE_TIMEOUT,
            retry_policy=RetryPolicy(
                maximum_attempts=5,
                non_retryable_error_types=NON_RETRYABLE_ERROR_TYPES,
            ),
        )
        return FlowRunWorkflowResult(
            flow_run_id=payload.flow_run_id,
            outcome=outcome,
            failure_reason=failure_reason,
            steps_executed=self._step_index,
        )
