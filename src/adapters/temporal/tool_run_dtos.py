from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Dict

from pydantic import BaseModel, Field

TOOL_RUN_TASK_QUEUE_DEFAULT = "tool-runs"


class ScheduledToolRunState(StrEnum):
    PENDING = "PENDING"
    WAITING = "WAITING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScheduledToolRunInput(BaseModel):
    tool_run_id: str
    tenant_id: str
    correlation_id: str
    run_at: datetime
    max_attempts: int = 3


class ScheduledToolRunResult(BaseModel):
    tool_run_id: str
    succeeded: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    failure_reason: str | None = None
