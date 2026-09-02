from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from domain.execution.services.graph_runtime.types import OperationStatus


class ToolExecutionMode(StrEnum):
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"


class ToolSchedulingError(StrEnum):
    SCHEDULER_UNAVAILABLE = "tool_scheduler_unavailable"
    SCHEDULE_FAILED = "tool_schedule_failed"
    RUN_AT_INVALID = "tool_schedule_run_at_invalid"
    RUN_AT_IN_THE_PAST = "tool_schedule_run_at_in_the_past"
    RUN_AT_MISSING = "tool_schedule_run_at_missing"


class ToolSchedulingConfig(BaseModel):
    mode: ToolExecutionMode = ToolExecutionMode.IMMEDIATE
    delay_seconds: int | None = Field(default=None, ge=0)
    run_at_param: str | None = None
    tool_names: list[str] | None = None


class ToolRunInput(BaseModel):
    operation_id: str
    tool_name: str
    tool_config_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    run_at: datetime | None = None


class ToolRunResult(BaseModel):
    operation_id: str
    tool_name: str
    execution_mode: ToolExecutionMode = ToolExecutionMode.IMMEDIATE
    status: OperationStatus
    result: dict[str, Any]
    schedule_id: str | None = None
    run_at: str | None = None


class ToolExecutorOutput(BaseModel):
    result: list[ToolRunResult] = Field(default_factory=list)
