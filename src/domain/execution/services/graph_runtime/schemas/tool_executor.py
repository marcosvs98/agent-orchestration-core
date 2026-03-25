from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from domain.execution.services.graph_runtime.types import OperationStatus


class ToolExecutionMode(StrEnum):
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"


class ToolRunInput(BaseModel):
    operation_id: str
    tool_name: str
    tool_config_id: str
    params: dict[str, Any] = Field(default_factory=dict)


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
