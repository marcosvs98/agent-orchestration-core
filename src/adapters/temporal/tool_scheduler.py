from __future__ import annotations

import asyncio
from uuid import UUID

import settings
from temporalio.client import Client
from temporalio.common import Priority, WorkflowIDReusePolicy

from adapters.temporal.client import build_temporal_client
from adapters.temporal.tool_run_dtos import ScheduledToolRunInput
from adapters.temporal.tool_run_workflow import ScheduledToolRunWorkflow
from domain.execution.ports.tool_run_scheduler import ToolRunSchedulerPort
from domain.execution.schemas.tool_schedule import (
    ToolRunSchedule,
    ToolRunScheduleRequest,
    tool_run_schedule_id_for,
)


class TemporalToolRunScheduler(ToolRunSchedulerPort):
    def __init__(self) -> None:
        self._client: Client | None = None
        self._connect_lock = asyncio.Lock()

    async def client(self) -> Client:
        if self._client is not None:
            return self._client
        async with self._connect_lock:
            if self._client is None:
                self._client = await build_temporal_client()
        return self._client

    async def schedule_tool_run(self, *, request: ToolRunScheduleRequest) -> ToolRunSchedule:
        client = await self.client()
        schedule_id = tool_run_schedule_id_for(str(request.tool_run_id))

        await client.start_workflow(
            ScheduledToolRunWorkflow.run,
            ScheduledToolRunInput(
                tool_run_id=str(request.tool_run_id),
                tenant_id=str(request.tenant_id),
                correlation_id=str(request.correlation_id),
                run_at=request.run_at,
                max_attempts=settings.TEMPORAL_TOOL_RUN_MAX_ATTEMPTS,
            ),
            id=schedule_id,
            task_queue=settings.TEMPORAL_TOOL_RUN_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            priority=self._priority(request.tenant_id),
        )

        return ToolRunSchedule(
            tool_run_id=request.tool_run_id,
            schedule_id=schedule_id,
            run_at=request.run_at,
        )

    async def cancel_tool_run_schedule(self, *, tool_run_id: UUID) -> None:
        client = await self.client()
        handle = client.get_workflow_handle(tool_run_schedule_id_for(str(tool_run_id)))
        await handle.cancel()

    @staticmethod
    def _priority(tenant_id: UUID) -> Priority | None:
        if not settings.TEMPORAL_FAIRNESS_ENABLED:
            return None
        return Priority(fairness_key=str(tenant_id))
