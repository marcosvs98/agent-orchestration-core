from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List, Protocol
from uuid import UUID

from pydantic import BaseModel, Field
from domain.prompts.schemas.prompt import NodeType
from domain.execution.services.graph_runtime.execution_plan import AvailableTool


class NodeExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    NEEDS_INPUT = "NEEDS_INPUT"


class IntentType(StrEnum):
    QUERY = "query"
    EXECUTION = "execution"
    GENERATION = "generation"
    TRANSFORMATION = "transformation"
    ANALYSIS = "analysis"
    CONVERSATION = "conversation"
    CONTROL = "control"


class IntentValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class UserContextEnrichmentMode(StrEnum):
    GATED = "GATED"
    LEGACY = "LEGACY"


class OperationStatus(StrEnum):
    """Lifecycle of an operation (execution level). Aligned with nodes.md §1.1."""

    READY = "ready"
    INCOMPLETE = "incomplete"
    SUCCESS = "success"
    ERROR = "error"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class ExecutionContext(BaseModel):
    """Immutable per-step context used by the runtime."""

    tenant_id: UUID
    user_id: str
    session_id: UUID
    input_payload: dict[str, Any] | None
    flow_id: UUID
    flow_version_id: UUID
    flow_run_id: UUID
    correlation_id: UUID
    trace_id: UUID | None = None
    current_node_id: str
    current_node_run_id: UUID | None = None
    available_tools: List[AvailableTool] = Field(default_factory=list)
    state: Dict[str, Any] = Field(default_factory=dict)
    memory: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    node_output: Dict[str, Any] = Field(default_factory=dict)
    iteration_counters: Dict[str, int] = Field(default_factory=dict)
    system_prompt: str | None = None
    system_context: str | None = None

    def snapshot(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    def get_node_output(self, node_type: NodeType) -> dict[str, Any]:
        out = self.state.get(node_type.value)
        if out is not None:
            return out
        out = self.state.get(node_type)
        return out if isinstance(out, dict) else {}


class NodeResult(BaseModel):
    """Canonical node execution result."""

    node: NodeType
    status: NodeExecutionStatus
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Dict[str, Any] | None = None
    metrics: Dict[str, Any] | None = None
    next_state: Dict[str, Any] | None = None
    memory_append: Dict[str, Any] | None = None


class NodeExecutor(Protocol):
    node_type: NodeType
    side_effect: bool
    deterministic: bool

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Execute a node using the provided context and configuration."""
