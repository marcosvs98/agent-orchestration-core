from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeBindingRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_id: UUID
    agent_version_id: UUID
    agent_version_is_active: bool


class ToolBindingDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_id: UUID
    name: str | None
    tool_config_id: UUID
    status: str


class TenantOperationalMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    sessions: int = 0
    end_users: int = 0
    sla_cases: int = 0
    flow_runs: int = 0
    interactions: int = 0
    response_artifacts: int = 0
    run_failures: int = 0


class PolicyActivationSets(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_published: frozenset[UUID]
    rate_limit_published: frozenset[UUID]
    billing_activated: frozenset[UUID]
    memory_activated: frozenset[UUID]
    rag_activated: frozenset[UUID]
    ai_execution_published: frozenset[UUID]
    execution_limit_published: frozenset[UUID]


class TenantOperationalDbSnapshot(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    flows: list[Any] = Field(default_factory=list)
    flow_resolved_version: dict[UUID, Any] = Field(default_factory=dict)
    flow_resolution_kind: dict[UUID, str] = Field(default_factory=dict)
    graphs_by_flow_version: dict[UUID, Any] = Field(default_factory=dict)
    drafts_by_flow_version: dict[UUID, Any] = Field(default_factory=dict)
    snapshots_by_flow_version: dict[UUID, Any] = Field(default_factory=dict)
    nodes_by_flow_version: dict[UUID, list[Any]] = Field(default_factory=dict)
    binding_by_node_id: dict[UUID, NodeBindingRow] = Field(default_factory=dict)
    ai_tasks_by_id: dict[UUID, Any] = Field(default_factory=dict)
    tool_bindings_by_agent_version: dict[UUID, list[ToolBindingDetail]] = Field(
        default_factory=dict
    )
    agents_with_active_version: list[Any] = Field(default_factory=list)
    published_flow_versions_count: int = 0
    nodes_total: int = 0
    agent_versions_total: int = 0
