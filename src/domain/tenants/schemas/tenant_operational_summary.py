from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentOperationalSummary(BaseModel):
    agent_id: UUID
    name: str | None = None
    agent_version_id: UUID | None = None
    agent_version_label: str | None = None
    ai_execution_policy_version_id: UUID | None = None
    rag_config_id: UUID | None = None
    status: str | None = None


class ResolvedFlowVersionBlock(BaseModel):
    flow_version_id: UUID
    resolution: str
    status: str
    version: str
    published_at: datetime | None = Field(
        default=None,
        description="activated_at when resolution is active_flow_version; created_at when latest_published",
    )


class FlowGraphSummary(BaseModel):
    present: bool
    node_count: int = 0
    edges_count: int = 0
    node_count_canonical: int = 0
    edges_count_canonical: int = 0
    node_count_draft: int = 0
    edges_count_draft: int = 0
    node_count_snapshot: int = 0
    edges_count_snapshot: int = 0
    start_node_id: UUID | None = None


class NodeAgentBindingSummary(BaseModel):
    agent_id: UUID
    agent_version_id: UUID
    agent_version_is_active: bool


class AiTaskOperationalSummary(BaseModel):
    allow_rag_tenant: bool = False
    allow_user_memory: bool = False
    allow_session_context: bool = False
    allow_memory_write: bool = False


class NodeToolBindingSummary(BaseModel):
    tool_id: UUID
    name: str | None = None
    tool_config_id: UUID
    status: str


class FlowNodeOperational(BaseModel):
    node_id: UUID
    node_type: str
    source_node_template_id: UUID | None = None
    ai_task: AiTaskOperationalSummary | None = None
    agent_binding: NodeAgentBindingSummary | None = None
    tool_bindings: list[NodeToolBindingSummary] = Field(default_factory=list)


class FlowOperational(BaseModel):
    id: UUID
    name: str
    resolved_flow_version: ResolvedFlowVersionBlock | None = None
    graph: FlowGraphSummary
    nodes: list[FlowNodeOperational] = Field(default_factory=list)


class PolicyRef(BaseModel):
    id: UUID
    name: str | None = None
    active: bool | None = Field(
        default=None,
        description=(
            "Runtime: status ACTIVE. Access/rate_limit/AI exec/exec limit: has "
            "PUBLISHED version. Billing/memory/rag: has activated version "
            "(is_active). Human SLA: policy.active flag."
        ),
    )


class TenantPoliciesOperational(BaseModel):
    runtime_policy: list[PolicyRef] = Field(default_factory=list)
    access_policy: list[PolicyRef] = Field(default_factory=list)
    rate_limit_policy: list[PolicyRef] = Field(default_factory=list)
    billing_policy: list[PolicyRef] = Field(default_factory=list)
    memory_policy: list[PolicyRef] = Field(default_factory=list)
    rag_policy: list[PolicyRef] = Field(default_factory=list)
    ai_execution_policy: list[PolicyRef] = Field(default_factory=list)
    execution_limit_policy: list[PolicyRef] = Field(default_factory=list)
    human_sla_policy: list[PolicyRef] = Field(default_factory=list)


class RagConfigSummaryItem(BaseModel):
    vector_store_id: UUID
    name: str
    rag_config_id: UUID
    status: str


class RagOperationalBlock(BaseModel):
    vector_stores_count: int = 0
    documents_count: int = 0
    chunks_count: int = 0
    rag_configs_count: int = 0
    configs: list[RagConfigSummaryItem] = Field(default_factory=list)


class ToolCapabilityItem(BaseModel):
    tool_id: UUID
    name: str | None = None
    tool_config_id: UUID
    status: str


class CapabilitiesBlock(BaseModel):
    tools: list[ToolCapabilityItem] = Field(default_factory=list)
    models_available_count: int = 0


class CountsBlock(BaseModel):
    active_agent_versions: int = 0
    published_flow_versions: int = 0
    flows_total: int = 0
    nodes_total: int = 0
    agent_versions_total: int = 0


class TenantMetricsBlock(BaseModel):
    sessions: int = 0
    end_users: int = 0
    sla_cases: int = 0
    flow_runs: int = 0
    interactions: int = 0
    response_artifacts: int = 0
    run_failures: int = 0


class TenantOperationalSummaryResponse(BaseModel):
    id: UUID
    external_id: UUID | None = None
    name: str
    description: str | None = None
    timezone: str
    is_active: bool
    currency: str
    language: str
    contact_name: str | None = None
    contact_phone: str | None = None
    settings: dict[str, object] | None = Field(
        default=None,
        description="Unstructured tenant configuration.",
    )
    agents: list[AgentOperationalSummary] = Field(default_factory=list)
    flows: list[FlowOperational] = Field(default_factory=list)
    policies: TenantPoliciesOperational = Field(
        default_factory=TenantPoliciesOperational
    )
    rag: RagOperationalBlock = Field(default_factory=RagOperationalBlock)
    capabilities: CapabilitiesBlock = Field(default_factory=CapabilitiesBlock)
    counts: CountsBlock = Field(default_factory=CountsBlock)
    metrics: TenantMetricsBlock = Field(default_factory=TenantMetricsBlock)
