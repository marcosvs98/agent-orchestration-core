from uuid import UUID

from enum import StrEnum
from pydantic import BaseModel, model_validator


class FlowFailureReason(StrEnum):
    POLICY_VIOLATION = "POLICY_VIOLATION"
    TIMEOUT = "TIMEOUT"
    STRUCTURAL_ERROR = "STRUCTURAL_ERROR"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    MISSING_GRAPH = "MISSING_GRAPH"
    MAX_STEPS_EXCEEDED = "MAX_STEPS_EXCEEDED"
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    UNKNOWN_NODE_TYPE = "UNKNOWN_NODE_TYPE"
    NO_MATCHING_EDGE = "NO_MATCHING_EDGE"
    MULTIPLE_MATCHING_EDGES = "MULTIPLE_MATCHING_EDGES"


class FlowRun(BaseModel):
    id: UUID
    origin_flow_run_id: UUID | None = None
    flow_version_id: UUID
    session_id: UUID
    interaction_id: UUID | None = None
    status: str
    canonical_status: str
    correlation_id: UUID
    started_at: str | None = None
    finished_at: str | None = None
    waiting_reason: str | None = None
    waiting_deadline_at: str | None = None
    input: dict[str, object]
    output: dict[str, object]
    error: dict[str, object]
    failure_reason: FlowFailureReason | None = None
    trace_id: UUID | None = None
    root_observation_id: str | None = None
    flow_graph_snapshot_id: UUID | None = None
    execution_plan_hash: str | None = None
    runtime_policy_hash: str | None = None
    tool_catalog_hash: str | None = None
    llm_provider_config_hash: str | None = None


class FlowRunInput(BaseModel):
    user_input: str | None = None


class FlowRunCreate(BaseModel):
    flow_id: UUID | None = None
    flow_version_id: UUID | None = None
    session_id: UUID
    origin_flow_run_id: UUID | None = None
    correlation_id: UUID | None = None
    input: FlowRunInput | None = None
    metadata: dict[str, object] = {}

    @model_validator(mode="after")
    def _validate_selector(self) -> "FlowRunCreate":
        if self.flow_id is None and self.flow_version_id is None:
            raise ValueError("flow_id_or_flow_version_id_required")
        return self


class GraphState(BaseModel):
    id: UUID
    flow_run_id: UUID
    state: dict[str, object]
    last_node_run_id: UUID | None = None


class NodeRun(BaseModel):
    id: UUID
    flow_run_id: UUID
    node_id: UUID
    status: str
    canonical_status: str
    correlation_id: UUID
    started_at: str | None = None
    finished_at: str | None = None
    input: dict[str, object]
    output: dict[str, object]
    error: dict[str, object]


class AgentRun(BaseModel):
    id: UUID
    node_run_id: UUID
    ai_task_id: UUID | None = None
    agent_version_id: UUID
    ai_execution_policy_version_id: UUID
    billing_policy_version_id: UUID | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    status: str
    canonical_status: str
    correlation_id: UUID
    started_at: str | None = None
    finished_at: str | None = None
    input: dict[str, object]
    output: dict[str, object]
    error: dict[str, object]
    system_prompt_hash: str | None = None


class AgentRunCreate(BaseModel):
    node_run_id: UUID
    agent_version_id: UUID
    ai_execution_policy_version_id: UUID
    correlation_id: UUID | None = None
    input: dict[str, object] = {}


class ToolRun(BaseModel):
    id: UUID
    tool_config_id: UUID
    agent_run_id: UUID | None = None
    node_run_id: UUID | None = None
    status: str
    canonical_status: str
    correlation_id: UUID
    started_at: str | None = None
    finished_at: str | None = None
    input: dict[str, object]
    output: dict[str, object]
    error: dict[str, object]
    idempotency_key: str | None = None
    has_side_effect: bool
    estimated_cost: float | None = None
    billing_policy_version_id: UUID | None = None


class ExecutionEvent(BaseModel):
    id: UUID
    tenant_id: UUID
    session_id: UUID
    flow_run_id: UUID
    type: str
    occurred_at: str
    event_sequence: int
    correlation_id: UUID
    causation_id: UUID | None = None
    schema_version: int
    payload: dict[str, object]
    node_id: UUID | None = None
    edge_id: str | None = None


class ToolRunCreate(BaseModel):
    tool_config_id: UUID
    agent_run_id: UUID | None = None
    node_run_id: UUID | None = None
    correlation_id: UUID | None = None
    input: dict[str, object] = {}
    has_side_effect: bool = False
