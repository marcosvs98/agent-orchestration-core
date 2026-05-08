from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from domain.user_input.schemas import MediaRefUserInputPart, TextUserInputPart


class SSEEventType(StrEnum):
    CONNECTED = "connected"
    TOOL_PROGRESS = "tool_progress"
    DONE = "done"
    ERROR = "error"
    PING = "ping"
    CONTENT_DELTA = "content_delta"


class ConversationRequest(BaseModel):
    agent_id: UUID
    session_id: UUID | None = None
    user_id: str
    user_input: str | None = None
    input_parts: list[TextUserInputPart | MediaRefUserInputPart] | None = None
    user_prompt_id: UUID | None = None
    correlation_id: UUID | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class ConversationEvent(BaseModel):
    event_type: SSEEventType
    payload: dict[str, Any] = Field(default_factory=dict)
