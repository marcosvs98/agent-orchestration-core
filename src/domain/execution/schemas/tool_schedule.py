from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

TOOL_RUN_SCHEDULE_ID_PREFIX = "tool-run-"


def tool_run_schedule_id_for(tool_run_id: str) -> str:
    return f"{TOOL_RUN_SCHEDULE_ID_PREFIX}{tool_run_id}"


class ToolRunScheduleRequest(BaseModel):
    tool_run_id: UUID
    tenant_id: UUID
    correlation_id: UUID
    run_at: datetime


class ToolRunSchedule(BaseModel):
    tool_run_id: UUID
    schedule_id: str
    run_at: datetime
