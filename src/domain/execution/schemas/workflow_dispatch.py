from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class FlowRunOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    WAITING = "WAITING"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class FlowRunDispatchRequest(BaseModel):
    flow_run_id: UUID
    tenant_id: UUID
    session_id: UUID
    user_id: str
    flow_id: UUID
    flow_version_id: UUID
    interaction_id: UUID
    correlation_id: UUID
    trace_id: UUID | None = None
    root_observation_id: str | None = None
    start_node_id: str | None = None
    channel: str = "http"
    idempotency_key: str | None = None
    run_timeout_ms: int | None = None
    turn_index: int = 0


class FlowRunDispatch(BaseModel):
    flow_run_id: UUID
    workflow_id: str
    run_id: str


class FlowRunDispatchStatus(BaseModel):
    flow_run_id: UUID
    workflow_id: str
    run_id: str
    outcome: FlowRunOutcome | None = None
    failure_reason: str | None = None
    steps_executed: int = 0
