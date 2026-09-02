from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.execution.schemas.tool_schedule import ToolRunSchedule, ToolRunScheduleRequest


class ToolRunSchedulerPort(Protocol):
    """Deferred execution of a already-created tool run.

    The tool run row is written before scheduling, so the schedule only carries
    identifiers. Implementations own durability of the wait and must execute the
    tool run exactly once per schedule id.
    """

    async def schedule_tool_run(self, *, request: ToolRunScheduleRequest) -> ToolRunSchedule: ...

    async def cancel_tool_run_schedule(self, *, tool_run_id: UUID) -> None: ...
