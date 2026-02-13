from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from infra.database.models.execution.flow_run import FlowRun as FlowRunModel


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


class Channel(StrEnum):
    HTTP = "http"
    WEBSOCKET = "websocket"
    AMQP = "amqp"
    GRPC = "grpc"


class FlowRun(BaseModel):
    id: UUID
    origin_flow_run_id: UUID | None = None
    flow_version_id: UUID
    session_id: UUID
    user_id: str
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

    @classmethod
    def from_model(
        cls, model: FlowRunModel, failure_reason: FlowFailureReason | None = None
    ) -> FlowRun:
        return cls(
            id=model.flow_run_id,
            origin_flow_run_id=model.origin_flow_run_id,
            flow_version_id=model.flow_version_id,
            session_id=model.session_id,
            user_id=model.user_id,
            interaction_id=model.interaction_id,
            status=model.status,
            canonical_status=model.canonical_status,
            correlation_id=model.correlation_id,
            started_at=model.started_at.isoformat() if model.started_at else None,
            finished_at=model.finished_at.isoformat() if model.finished_at else None,
            waiting_reason=model.waiting_reason,
            waiting_deadline_at=model.waiting_deadline_at.isoformat()
            if model.waiting_deadline_at
            else None,
            input=model.input or {},
            output=model.output or {},
            error=model.error or {},
            failure_reason=failure_reason,
            trace_id=model.trace_id,
            root_observation_id=model.root_observation_id,
            flow_graph_snapshot_id=model.flow_graph_snapshot_id,
            execution_plan_hash=model.execution_plan_hash,
            runtime_policy_hash=model.runtime_policy_hash,
            tool_catalog_hash=model.tool_catalog_hash,
            llm_provider_config_hash=model.llm_provider_config_hash,
        )


class FlowRunInput(BaseModel):
    user_input: str | None = None


class FlowRunCreate(BaseModel):
    flow_id: UUID | None = None
    flow_version_id: UUID | None = None
    session_id: UUID
    user_id: str
    origin_flow_run_id: UUID | None = None
    correlation_id: UUID | None = None
    input: FlowRunInput | None = None
    metadata: dict[str, object] = {}

    @model_validator(mode="after")
    def _validate_selector(self) -> "FlowRunCreate":
        if self.flow_id is None and self.flow_version_id is None:
            raise ValueError("flow_id_or_flow_version_id_required")
        if not self.user_id.strip():
            raise ValueError("user_id_required")
        return self


class FlowRunResumeInput(BaseModel):
    user_id: str
    user_input: str | None = None

    @model_validator(mode="after")
    def _validate_user_id(self) -> "FlowRunResumeInput":
        if not self.user_id.strip():
            raise ValueError("user_id_required")
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
    user_id: str
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


class UserPreferenceUpsertResult(BaseModel):
    """Result of upserting a user preference (insert or update)."""

    model_config = ConfigDict(frozen=True)

    updated: bool
    version: int
    previous_source: str | None
    reason: str | None = None
