from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentTurnRole(StrEnum):
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AgentToolDefinition(BaseModel):
    """One callable capability offered to the model for a single turn.

    ``name`` is the runtime-facing identifier the model must echo back in a tool call; the
    runtime resolves it against the run's authorized grant, never against the agent catalogue.
    """

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class AgentToolCall(BaseModel):
    call_id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_arguments: str = ""

    model_config = {"frozen": True}


class AgentTurnMessage(BaseModel):
    role: AgentTurnRole
    content: str | None = None
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    tool_name: str | None = None

    model_config = {"frozen": True}


class AgentTurnRequest(BaseModel):
    model_alias: str
    messages: list[AgentTurnMessage] = Field(default_factory=list)
    tools: list[AgentToolDefinition] = Field(default_factory=list)
    temperature: float = 0.2
    max_output_tokens: int | None = None
    principal_id: str | None = None
    prompt_cache_key: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = {"frozen": True}


class AgentTurnStopReason(StrEnum):
    TOOL_CALLS = "tool_calls"
    OUTPUT = "output"


class AgentTurnCompletion(BaseModel):
    text: str = ""
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    stop_reason: AgentTurnStopReason = AgentTurnStopReason.OUTPUT
    token_usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float | None = None
    model_alias: str = ""
    provider_response_id: str | None = None

    model_config = {"frozen": True}
