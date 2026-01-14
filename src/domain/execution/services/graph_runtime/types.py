from __future__ import annotations

from typing import Any, Dict, List, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    """Immutable per-step context used by the runtime."""

    tenant_id: UUID
    session_id: UUID
    flow_id: UUID
    flow_version_id: UUID
    flow_run_id: UUID
    correlation_id: UUID
    trace_id: UUID | None = None
    current_node_id: str
    state: Dict[str, Any] = Field(default_factory=dict)
    memory: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    node_output: Dict[str, Any] = Field(default_factory=dict)
    iteration_counters: Dict[str, int] = Field(default_factory=dict)


class NodeResult(BaseModel):
    """Canonical node execution result."""

    status: Literal["SUCCESS", "ERROR", "NEEDS_INPUT"]
    payload: Dict[str, Any] = Field(default_factory=dict)
    error: Dict[str, Any] | None = None
    metrics: Dict[str, Any] | None = None
    next_state: Dict[str, Any] | None = None
    memory_append: Dict[str, Any] | None = None


class NodeExecutor(Protocol):
    node_type: str
    side_effect: bool
    deterministic: bool

    async def execute(self, context: ExecutionContext, config: Dict[str, Any] | None = None) -> NodeResult:
        """Execute a node using the provided context and configuration."""
