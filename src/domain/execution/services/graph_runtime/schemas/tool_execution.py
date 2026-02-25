from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from domain.execution.services.graph_runtime.types import OperationStatus


class ToolRunInput(BaseModel):
    operation_id: str
    tool_name: str
    tool_config_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class ToolRunResult(BaseModel):
    operation_id: str
    tool_name: str
    execution_mode: Literal["immediate", "scheduled"] = "immediate"
    status: OperationStatus
    result: dict[str, Any]
    schedule_id: str | None = None
    run_at: str | None = None


class ToolExecutionNodeOutput(BaseModel):
    result: list[ToolRunResult] = Field(default_factory=list)
