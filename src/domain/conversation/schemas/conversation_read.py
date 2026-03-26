from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InteractionReadRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    interaction_id: UUID
    session_id: UUID
    flow_run_id: UUID | None
    result_node_run_id: UUID | None
    channel: str
    received_at: datetime
    completed_at: datetime | None = None
    external_message_id: str | None
    request_id: str | None
    trace_id: str | None
    payload: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    headers: dict[str, Any] | None = None


class InteractionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    interaction_id: UUID
    session_id: UUID
    flow_run_id: UUID | None
    result_node_run_id: UUID | None
    channel: str
    received_at: datetime
    completed_at: datetime | None = None
    external_message_id: str | None
    request_id: str | None
    trace_id: str | None
    user_input: Any | None = None
    system_output: str | None = None


class PaginatedInteractionsResponse(BaseModel):
    items: list[InteractionSummary]
    limit: int
    offset: int
    has_next: bool


class SessionReadRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: UUID
    user_id: str


class SessionSummary(SessionReadRecord):
    pass


class PaginatedSessionsResponse(BaseModel):
    items: list[SessionSummary]
    limit: int
    offset: int
    has_next: bool


class EndUserReadRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    end_user_id: UUID
    user_id: str


class EndUserListItem(EndUserReadRecord):
    pass


class PaginatedEndUsersResponse(BaseModel):
    items: list[EndUserReadRecord]
    limit: int
    offset: int
    has_next: bool


class EndUserDetailResponse(BaseModel):
    end_user_id: UUID
    user_id: str = Field(max_length=255)
    preferences: dict[str, Any]
    memory_profile: dict[str, Any]
