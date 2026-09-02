from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeStatusLiteral = Literal["SUCCESS", "ERROR", "NEEDS_INPUT"]
OutcomeLiteral = Literal["COMPLETED", "WAITING", "FAILED", "CANCELLED"]

TASK_QUEUE_DEFAULT = "flow-runs"
WORKFLOW_ID_PREFIX = "flow-run-"


def workflow_id_for(flow_run_id: str, turn_index: int = 0) -> str:
    if turn_index <= 0:
        return f"{WORKFLOW_ID_PREFIX}{flow_run_id}"
    return f"{WORKFLOW_ID_PREFIX}{flow_run_id}-t{turn_index}"


class FlowRunWorkflowInput(BaseModel):
    flow_run_id: str
    tenant_id: str
    session_id: str
    user_id: str
    flow_id: str
    flow_version_id: str
    interaction_id: str
    correlation_id: str
    trace_id: str | None = None
    root_observation_id: str | None = None
    start_node_id: str | None = None
    channel: str = "http"
    idempotency_key: str | None = None
    turn_index: int = 0


class FlowRunPlanSummary(BaseModel):
    start_node_id: str
    max_steps: int
    loop_limit: int
    node_count: int
    max_node_duration_ms: int
    max_total_duration_ms: int
    llm_max_retries: int
    tools_max_retries: int


class ExecuteNodeInput(BaseModel):
    flow_run_id: str
    tenant_id: str
    flow_id: str
    node_id: str
    step_index: int
    loop_limit: int = 10
    trace_id: str | None = None
    parent_observation_id: str | None = None


class ExecuteNodeOutput(BaseModel):
    node_type: str
    node_run_id: str | None = None
    status: NodeStatusLiteral
    terminal: bool = False
    next_node_id: str | None = None
    loop_edge_keys: list[str] = Field(default_factory=list)
    failure_reason: str | None = None
    resume_to_node_id: str | None = None


class FinalizeFlowRunInput(BaseModel):
    flow_run_id: str
    tenant_id: str
    session_id: str
    user_id: str
    correlation_id: str
    outcome: OutcomeLiteral
    failure_reason: str | None = None
    last_node_id: str | None = None
    last_node_run_id: str | None = None
    idempotency_key: str | None = None


class FlowRunWorkflowResult(BaseModel):
    flow_run_id: str
    outcome: OutcomeLiteral
    failure_reason: str | None = None
    steps_executed: int = 0


class FlowRunProgress(BaseModel):
    flow_run_id: str
    step_index: int
    current_node_id: str | None = None
    outcome: OutcomeLiteral | None = None
