from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.agents.schemas.a2a import A2AArtifact


class AgentToolCallStatus(StrEnum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    ERROR = "ERROR"


class AgentRunScope(BaseModel):
    """Identity every step of one execution is attributed to."""

    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    principal_id: str
    agent_run_id: UUID
    agent_id: UUID
    correlation_id: UUID
    root_agent_run_id: UUID
    delegation_depth: int = 0
    interaction_metadata: dict[str, str] = Field(default_factory=dict)


class ToolCallOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    function_name: str
    status: AgentToolCallStatus
    result_text: str
    tool_run_id: UUID | None = None
    tool_config_id: UUID | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)
    child_agent_run_id: UUID | None = None
    a2a_task_id: str | None = None
    artifacts: list[A2AArtifact] = Field(default_factory=list)
