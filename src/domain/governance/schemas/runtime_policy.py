from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RuntimePolicyScope(StrEnum):
    TENANT = "TENANT"
    FLOW = "FLOW"


class RuntimePolicySource(StrEnum):
    FLOW = "FLOW"
    TENANT = "TENANT"
    DEFAULT = "DEFAULT"


class RuntimePolicyDefinition(BaseModel):
    limits: Dict[str, Any] = Field(default_factory=dict)
    execution: Dict[str, Any] = Field(default_factory=dict)
    tools: Dict[str, Any] = Field(default_factory=dict)
    llm: Dict[str, Any] = Field(default_factory=dict)


class ResolvedRuntimePolicy(BaseModel):
    source: RuntimePolicySource
    runtime_policy_id: Optional[UUID] = None
    version: str
    definition: RuntimePolicyDefinition
    scope: RuntimePolicyScope
    flow_id: Optional[UUID] = None
