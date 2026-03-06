from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SSEEventType(StrEnum):
    CONNECTED = "connected"
    FLOW_STARTED = "flow_started"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    EDGE_EVALUATED = "edge_evaluated"
    FLOW_COMPLETED = "flow_completed"
    FLOW_FAILED = "flow_failed"
    DONE = "done"
    ERROR = "error"
    PING = "ping"


class ConversationRequest(BaseModel):
    flow_id: UUID | None = None
    flow_version_id: UUID | None = None
    session_id: UUID | None = None
    user_id: str
    user_input: str | None = None
    correlation_id: UUID | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class ConversationEvent(BaseModel):
    event_type: SSEEventType
    payload: dict[str, Any] = Field(default_factory=dict)
