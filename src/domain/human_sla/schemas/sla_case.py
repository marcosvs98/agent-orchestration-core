from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SLAStatus(StrEnum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class SLAFallbackReason(StrEnum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    TOOL_FAILURE = "TOOL_FAILURE"
    TIMEOUT = "TIMEOUT"
    EXECUTION_LIMIT = "EXECUTION_LIMIT"
    POLICY_BLOCK = "POLICY_BLOCK"
    UNKNOWN_INTENT = "UNKNOWN_INTENT"
    USER_REQUESTED_HUMAN = "USER_REQUESTED_HUMAN"
    USER_FRUSTRATION = "USER_FRUSTRATION"
    USER_ANGER = "USER_ANGER"
    USER_INSULT = "USER_INSULT"


class SeverityLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SLAResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    TRANSFERRED = "TRANSFERRED"
    USER_ABANDONED = "USER_ABANDONED"


class SLACaseCreate(BaseModel):
    tenant_id: UUID
    session_id: UUID
    flow_run_id: UUID
    node_run_id: UUID
    interaction_id: UUID | None = None
    user_id: str
    priority: str | None = None
    fallback_reason: SLAFallbackReason = SLAFallbackReason.UNKNOWN_INTENT
    opened_at: datetime
    sla_target_at: datetime | None = None
    human_sla_policy_id: UUID | None = None
    current_escalation_level: int = 0


class SLACaseAssign(BaseModel):
    human_agent_id: str = Field(min_length=1, max_length=128)


class SLACaseResolve(BaseModel):
    resolution_status: SLAResolutionStatus
    resolution_summary: str = Field(min_length=1, max_length=1024)
    human_agent_id: str = Field(min_length=1, max_length=128)


class SLACaseListFilter(BaseModel):
    status: SLAStatus | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    session_id: UUID | None = None


class SLACaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sla_case_id: UUID
    tenant_id: UUID
    session_id: UUID
    flow_run_id: UUID
    node_run_id: UUID
    interaction_id: UUID | None
    user_id: str
    status: SLAStatus
    priority: str | None
    fallback_reason: SLAFallbackReason
    human_agent_id: str | None
    resolution_status: SLAResolutionStatus | None
    resolution_summary: str | None
    opened_at: datetime
    assigned_at: datetime | None
    resolved_at: datetime | None
    sla_target_at: datetime | None
    sla_breached: bool
    human_sla_policy_id: UUID | None
    current_escalation_level: int
    created_at: datetime
    updated_at: datetime
