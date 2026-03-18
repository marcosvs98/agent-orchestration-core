from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class HumanSLAEscalationRule(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    human_sla_escalation_rule_id: UUID
    human_sla_policy_id: UUID
    level: int
    trigger_after_hours: int
    new_priority: str


class HumanSLAPolicy(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    human_sla_policy_id: UUID
    tenant_id: UUID
    name: str
    node: str
    fallback_reason: str
    initial_priority: str
    target_response_hours: int | None
    target_resolution_hours: int | None
    active: bool
    created_at: datetime
    updated_at: datetime
    escalation_rules: list[HumanSLAEscalationRule] = []
