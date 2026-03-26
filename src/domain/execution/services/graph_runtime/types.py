from __future__ import annotations

from enum import StrEnum
from collections.abc import Awaitable, Callable
from typing import Any, Dict, List, Protocol
from uuid import UUID

from pydantic import BaseModel, Field
from domain.prompts.schemas.prompt import NodeType
from domain.execution.services.graph_runtime.execution_plan import AvailableTool

USER_CONTEXT_READ_GATE_STATE_KEY = "user_context_enrichment"
NODE_OUTPUTS_BY_NODE_ID_KEY = "_node_outputs_by_node_id"
MEMORY_CONTENT_SUMMARIZE_STAGING_KEY = "_MEMORY_CONTENT_SUMMARIZE_input"


class NodeExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    NEEDS_INPUT = "NEEDS_INPUT"


class IntentType(StrEnum):
    QUERY = "query"
    COMMAND = "command"
    GENERATION = "generation"
    TRANSFORMATION = "transformation"
    ANALYSIS = "analysis"
    CONVERSATION = "conversation"
    CONTROL = "control"
    UPDATE_USER_PREFERENCES = "update_user_preferences"


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


class ToolSelectionMode(StrEnum):  # Todo: Depreciar se não for mais utilizado
    """How tool selection was decided. Used for observability and tracing."""

    SEMANTIC_NOOP = "semantic_noop"
    SINGLE_TOOL_AUTO_SELECT = "single_tool_auto_select"
    SINGLE_CANDIDATE_NO_LLM = "single_candidate_no_llm"
    HEURISTIC_AUTO_SELECT = "heuristic_auto_select"
    SEMANTIC = "semantic"
    LLM_FALLBACK = "llm_fallback"
    RAG_WITH_LLM = "rag_with_llm"


class ToolSelectionReason(StrEnum):  # Todo: Depreciar se não for mais utilizado
    """Reason for the tool selection outcome. Used for observability and tracing."""

    MISSING_USER_INPUT = "missing_user_input"
    SINGLE_TOOL_AFTER_INTENT_FILTER = "single_tool_after_intent_filter"
    NO_TOOLS_AFTER_INTENT_FILTER = "no_tools_after_intent_filter"
    RAG_CONFIG_NOT_FOUND = "rag_config_not_found"
    RAG_RETURNED_NO_CANDIDATES = "rag_returned_no_candidates"
    NO_SEMANTIC_EVIDENCE_BUT_SINGLE_CANDIDATE = (
        "no_semantic_evidence_but_single_candidate"
    )
    ABOVE_CONFIDENCE_THRESHOLD = "above_confidence_threshold"
    BELOW_CONFIDENCE_THRESHOLD = "below_confidence_threshold"
    LLM_SELECTION = "llm_selection"


class ToolIntentFilter(StrEnum):
    QUERY = "query"
    COMMAND = "command"


class IntentClassificationMode(StrEnum):
    HEURISTIC = "heuristic"
    SEMANTIC = "semantic"
    LLM_FALLBACK = "llm_fallback"
    DEFAULT = "default"


class IntentClassificationReason(StrEnum):
    EMPTY_USER_INPUT = "empty_user_input"
    RAG_CONFIG_NOT_FOUND = "rag_config_not_found"
    NO_SEMANTIC_MATCH = "no_semantic_match"
    ABOVE_CONFIDENCE_THRESHOLD = "above_confidence_threshold"
    BELOW_CONFIDENCE_THRESHOLD = "below_confidence_threshold"
    LLM_FALLBACK_UNAVAILABLE = "llm_fallback_unavailable"


class RuntimeTraceEdgeEventStatus(StrEnum):
    RECORDED = "recorded"


class ExecutionContext(BaseModel):
    """Immutable per-step context used by the runtime."""

    tenant_id: UUID
    interaction_id: UUID
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
    on_content_delta: Callable[[str], Awaitable[None]] | None = Field(
        default=None, exclude=True
    )

    def snapshot(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    def get_node_output(self, node_type: NodeType) -> dict[str, Any]:
        out = self.state.get(node_type.value)
        if out is not None:
            return out
        out = self.state.get(node_type)
        return out if isinstance(out, dict) else {}


class NodeResult(BaseModel):
    node: NodeType
    status: NodeExecutionStatus
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Dict[str, Any] | None = None
    metrics: Dict[str, Any] | None = None
    next_state: Dict[str, Any] | None = None
    memory: List[Dict[str, Any]] | None = None


class NodeExecutor(Protocol):
    node_type: NodeType
    side_effect: bool
    deterministic: bool

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Execute a node using the provided context and configuration."""
