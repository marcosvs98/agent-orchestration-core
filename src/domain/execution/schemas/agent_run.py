from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_MAX_ITERATIONS = 8
MAX_ALLOWED_ITERATIONS = 25
DELEGATION_TOOL_NAME = "delegate_to_agent"


class AgentRunOrigin(StrEnum):
    FLOW_NODE = "FLOW_NODE"
    DIRECT = "DIRECT"
    A2A_DELEGATION = "A2A_DELEGATION"


class AgentRunFinishReason(StrEnum):
    FINAL_OUTPUT = "FINAL_OUTPUT"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    LLM_ERROR = "LLM_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    CANCELLED = "CANCELLED"


class AgentRunTrustLevel(StrEnum):
    TRUSTED_INSTRUCTION = "trusted_instruction"
    TENANT_MANAGED = "tenant_managed"
    CALLER_SUPPLIED = "caller_supplied"
    TOOL_RESULT = "tool_result"


class AgentRunContextItem(BaseModel):
    """One piece of context scoped to a single execution.

    Never merged into the agent's published configuration: it lives on the run, is replayed from
    the run's own snapshot, and is labelled ``caller_supplied`` so the prompt keeps the
    distinction between what the tenant authored and what the caller passed in.
    """

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=20000)
    description: str | None = Field(default=None, max_length=512)


class AgentRunToolGrant(BaseModel):
    """Which capabilities this execution may use.

    ``allowed_tool_names`` omitted means every tool bound to the agent version; an empty list
    means none. Either way the resolved grant is frozen onto the run and every dispatch is
    checked against it, so the model cannot reach a tool the caller did not authorize.
    """

    model_config = ConfigDict(frozen=True)

    allowed_tool_names: list[str] | None = None
    allow_agent_delegation: bool = False
    delegate_agent_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_delegation(self) -> AgentRunToolGrant:
        if self.allow_agent_delegation and not self.delegate_agent_ids:
            raise ValueError("delegate_agent_ids_required_when_delegation_allowed")
        return self


class AgentRunCreate(BaseModel):
    agent_id: UUID
    instruction: str = Field(min_length=1, max_length=20000)
    payload: dict[str, Any] = Field(default_factory=dict)
    context: list[AgentRunContextItem] = Field(default_factory=list, max_length=50)
    tools: AgentRunToolGrant = Field(default_factory=AgentRunToolGrant)
    max_iterations: int | None = Field(default=None, ge=1, le=MAX_ALLOWED_ITERATIONS)
    correlation_id: UUID | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class AgentRunToolCall(BaseModel):
    tool_run_id: UUID | None = None
    tool_call_id: str
    tool_name: str
    tool_config_id: UUID | None = None
    status: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)


class AgentRunMessage(BaseModel):
    sequence: int
    role: str
    content: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    trust_level: str | None = None
    source: str | None = None


class AgentRunEvent(BaseModel):
    sequence: int
    type: str
    occurred_at: str
    correlation_id: UUID
    causation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentRunArtifact(BaseModel):
    artifact_id: str
    index: int
    name: str | None = None
    description: str | None = None
    parts: list[dict[str, Any]] = Field(default_factory=list)


class AgentRunDelegation(BaseModel):
    agent_delegation_id: UUID
    a2a_task_id: str
    a2a_context_id: str
    a2a_task_state: str
    transport: str
    target_agent_id: UUID | None = None
    child_agent_run_id: UUID | None = None


class AgentRunSummary(BaseModel):
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    origin: AgentRunOrigin
    status: str
    canonical_status: str
    correlation_id: UUID
    node_run_id: UUID | None = None
    parent_agent_run_id: UUID | None = None
    root_agent_run_id: UUID | None = None
    delegation_depth: int = 0
    model: str | None = None
    max_iterations: int | None = None
    iterations_used: int = 0
    finish_reason: AgentRunFinishReason | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    started_at: str | None = None
    finished_at: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)


class AgentRunDetail(AgentRunSummary):
    input: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    tool_grant: dict[str, Any] = Field(default_factory=dict)
    messages: list[AgentRunMessage] = Field(default_factory=list)
    tool_calls: list[AgentRunToolCall] = Field(default_factory=list)
    events: list[AgentRunEvent] = Field(default_factory=list)
    artifacts: list[AgentRunArtifact] = Field(default_factory=list)
    delegations: list[AgentRunDelegation] = Field(default_factory=list)
