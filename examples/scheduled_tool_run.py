from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Final
from uuid import uuid4

from examples.support import NullTracer, expect, field, heading

import settings
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from adapters.temporal.sandbox import build_workflow_runner
from adapters.temporal.tool_run_activities import ScheduledToolRunActivities
from adapters.temporal.tool_run_dtos import ScheduledToolRunInput, ScheduledToolRunState
from adapters.temporal.tool_run_workflow import ScheduledToolRunWorkflow

TASK_QUEUE: Final[str] = "examples-tool-runs"
WAIT_SECONDS: Final[int] = 4


class DemoOrchestrator:
    def __init__(self) -> None:
        self.executed_at: datetime | None = None

    async def execute_tool_run(self, *, tool_run_id: Any) -> dict[str, Any]:
        self.executed_at = datetime.now(timezone.utc)
        return {"tool_run_id": str(tool_run_id), "charged": True}


async def main() -> None:
    print("ToolExecutionMode.SCHEDULED: deferred side effects on a durable timer")
    print(f"temporal host = {settings.TEMPORAL_HOST}")

    try:
        client = await Client.connect(
            settings.TEMPORAL_HOST,
            namespace=settings.TEMPORAL_NAMESPACE,
            data_converter=pydantic_data_converter,
        )
    except Exception as exc:
        raise SystemExit(
            f"cannot reach Temporal at {settings.TEMPORAL_HOST}: {exc}\n"
            "start it with: docker compose up -d temporal"
        ) from exc

    orchestrator = DemoOrchestrator()
    activities = ScheduledToolRunActivities(
        tool_orchestrator=orchestrator,
        tracer=NullTracer(),
    )

    tool_run_id = uuid4()
    run_at = datetime.now(timezone.utc) + timedelta(seconds=WAIT_SECONDS)
    workflow_id = f"example-tool-run-{tool_run_id}"

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflow_runner=build_workflow_runner(),
        workflows=[ScheduledToolRunWorkflow],
        activities=[activities.execute_scheduled_tool_run],
    ):
        heading("Scheduling")
        field("tool_run_id", tool_run_id)
        field("run_at", run_at.isoformat())
        started_at = datetime.now(timezone.utc)

        handle = await client.start_workflow(
            ScheduledToolRunWorkflow.run,
            ScheduledToolRunInput(
                tool_run_id=str(tool_run_id),
                tenant_id=str(uuid4()),
                correlation_id=str(uuid4()),
                run_at=run_at,
                max_attempts=3,
            ),
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        heading("While the timer is pending")
        await asyncio.sleep(1)
        state = await handle.query(ScheduledToolRunWorkflow.get_state)
        field("workflow state", state)
        field("tool executed yet", orchestrator.executed_at is not None)
        expect(state == ScheduledToolRunState.WAITING, "the workflow is parked on a durable timer")
        expect(orchestrator.executed_at is None, "the side effect has NOT happened yet")

        heading("After the timer fires")
        result = await handle.result()
        executed_at = orchestrator.executed_at
        if executed_at is None:
            raise SystemExit("FAILED: the workflow finished but the tool was never executed")
        elapsed = (executed_at - started_at).total_seconds()
        field("workflow state", await handle.query(ScheduledToolRunWorkflow.get_state))
        field("succeeded", result.succeeded)
        field("output", result.output)
        field("elapsed before execution (s)", round(elapsed, 2))
        expect(result.succeeded, "the tool ran when the schedule fired")
        expect(
            elapsed >= WAIT_SECONDS - 1,
            f"execution was deferred by roughly {WAIT_SECONDS}s",
        )

    print()
    print(f"Inspect the run at http://localhost:8233 (workflow id {workflow_id})")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
