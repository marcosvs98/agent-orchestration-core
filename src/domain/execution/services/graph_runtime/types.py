from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List, Protocol
from uuid import UUID

from pydantic import BaseModel, Field
from domain.prompts.schemas.prompt import NodeType  # Todo: Isso não esta coeso
from domain.execution.services.graph_runtime.execution_plan import AvailableTool


class NodeExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    NEEDS_INPUT = "NEEDS_INPUT"


class ExecutionContext(BaseModel):
    """Immutable per-step context used by the runtime."""

    tenant_id: UUID
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


class NodeResult(BaseModel):
    """Canonical node execution result."""

    status: NodeExecutionStatus
    payload: Dict[str, Any] = Field(default_factory=dict)
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
