from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from adapters.temporal.tool_run_activities import ScheduledToolRunActivities
    from adapters.temporal.tool_run_dtos import (
        ScheduledToolRunInput,
        ScheduledToolRunResult,
        ScheduledToolRunState,
    )

TOOL_RUN_NON_RETRYABLE_ERROR_TYPES = [
    "DomainValidationException",
    "NotFoundServiceException",
]

TOOL_RUN_EXECUTE_TIMEOUT = timedelta(minutes=5)
MAX_SCHEDULE_HORIZON = timedelta(days=365)


@workflow.defn
class ScheduledToolRunWorkflow:
    """Durable timer plus one tool execution.

    The wait is a server-side timer, so a worker restart does not lose the
    schedule. Execution happens in an activity because it performs the external
    side effect and every database write for the tool run.
    """

    def __init__(self) -> None:
        self._state: str = ScheduledToolRunState.PENDING.value
        self._tool_run_id: str = ""

    @workflow.query
    def get_state(self) -> ScheduledToolRunState:
        return ScheduledToolRunState(self._state)

    @workflow.run
    async def run(self, payload: ScheduledToolRunInput) -> ScheduledToolRunResult:
        self._tool_run_id = payload.tool_run_id

        delay = payload.run_at - workflow.now()
        if delay > MAX_SCHEDULE_HORIZON:
            delay = MAX_SCHEDULE_HORIZON
        if delay.total_seconds() > 0:
            self._state = ScheduledToolRunState.WAITING.value
            await workflow.sleep(delay)

        self._state = ScheduledToolRunState.EXECUTING.value
        output = await workflow.execute_activity_method(
            ScheduledToolRunActivities.execute_scheduled_tool_run,
            payload,
            start_to_close_timeout=TOOL_RUN_EXECUTE_TIMEOUT,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=payload.max_attempts,
                non_retryable_error_types=TOOL_RUN_NON_RETRYABLE_ERROR_TYPES,
            ),
        )

        self._state = (
            ScheduledToolRunState.COMPLETED.value
            if output.succeeded
            else ScheduledToolRunState.FAILED.value
        )
        return output
