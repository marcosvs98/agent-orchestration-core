from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class Flow(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    tags: list[str] | None = None
    created_by: str | None = None


class FlowCreate(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] | None = None


class FlowVersion(BaseModel):
    id: UUID
    flow_id: UUID
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None
    min_agent_version_major: int | None = None
    min_agent_version_minor: int | None = None
    min_agent_version_patch: int | None = None


class FlowVersionCreate(BaseModel):
    source_version_id: UUID | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None
    min_agent_version_major: int | None = None
    min_agent_version_minor: int | None = None
    min_agent_version_patch: int | None = None


class Node(BaseModel):
    id: UUID
    flow_version_id: UUID
    node_prompt_id: UUID
    allow_rag_tenant: bool = False
    allow_user_memory_structured: bool = False
    allow_user_memory_vector: bool = False
    rag_config_id: UUID | None = None
    allow_session_context: bool = False
    allow_memory_write: bool = False


class NodeCreate(BaseModel):
    flow_version_id: UUID
    node_prompt_id: UUID
    allow_rag_tenant: bool = False
    allow_user_memory_structured: bool = False
    allow_user_memory_vector: bool = False
    rag_config_id: UUID | None = None
    allow_session_context: bool = False
    allow_memory_write: bool = False


class Router(BaseModel):
    id: UUID
    node_id: UUID


class RouterCreate(BaseModel):
    node_id: UUID


class ConditionExpression(BaseModel):
    id: UUID
    expression: str | None = None


class ConditionExpressionCreate(BaseModel):
    expression: str | None = None


class RoutingRule(BaseModel):
    id: UUID
    router_id: UUID
    condition_expression_id: UUID
    from_node_id: UUID
    to_node_id: UUID


class RoutingRuleCreate(BaseModel):
    router_id: UUID
    condition_expression_id: UUID
    from_node_id: UUID
    to_node_id: UUID


class NodeTemplateCatalogItem(BaseModel):
    id: UUID
    code: str
    node_type: str
    default_config: Dict[str, Any] | None = None


class NodeTemplateCopyRequest(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    node_template_id: UUID | None = None
    code: str | None = None
    overrides: Dict[str, Any] | None = None
    allow_rag_tenant: bool = False
    allow_user_memory_structured: bool = False
    allow_user_memory_vector: bool = False
    rag_config_id: UUID | None = None
    allow_session_context: bool = False
    allow_memory_write: bool = False


class CustomNodeCreate(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    node_type: str
    node_prompt_id: UUID
    config: Dict[str, Any] | None = None
    allow_rag_tenant: bool = False
    allow_user_memory_structured: bool = False
    allow_user_memory_vector: bool = False
    rag_config_id: UUID | None = None
    allow_session_context: bool = False
    allow_memory_write: bool = False


class DeploymentComposeBinding(BaseModel):
    binding_key: str
    value_type: str
    source_kind: str
    value: Dict[str, Any]


class DeploymentComposeRequest(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    principal_id: str
    environment: str = "default"
    graph_definition: Dict[str, Any]
    runtime_policy_definition: Dict[str, Any] | None = None
    tool_catalog: Dict[str, Any] | None = None
    llm_provider_config_hash: str | None = None
    bindings: list[DeploymentComposeBinding] = Field(default_factory=list)


class DeploymentComposeResponse(BaseModel):
    flow_snapshot_id: UUID
    flow_deployment_id: UUID
    flow_version_id: UUID
    environment: str


class DeploymentComposeValidateResponse(BaseModel):
    valid: bool
    snapshot_hash: str


class FlowArtifactsBatchUpsertRequest(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    principal_id: str
    nodes_from_templates: list[NodeTemplateCopyRequest] = Field(default_factory=list)
    custom_nodes: list[CustomNodeCreate] = Field(default_factory=list)
    routers: list[RouterCreate] = Field(default_factory=list)
    condition_expressions: list[ConditionExpressionCreate] = Field(default_factory=list)
    routing_rules: list[RoutingRuleCreate] = Field(default_factory=list)


class FlowArtifactsBatchUpsertResponse(BaseModel):
    nodes_created: int
    routers_created: int
    condition_expressions_created: int
    routing_rules_created: int
