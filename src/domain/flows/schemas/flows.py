from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel


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
    allow_user_memory: bool = False
    allow_session_context: bool = False
    allow_memory_write: bool = False


class NodeCreate(BaseModel):
    flow_version_id: UUID
    node_prompt_id: UUID
    allow_rag_tenant: bool = False
    allow_user_memory: bool = False
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
    allow_user_memory: bool = False
    allow_session_context: bool = False
    allow_memory_write: bool = False


class CustomNodeCreate(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    node_type: str
    node_prompt_id: UUID
    config: Dict[str, Any] | None = None
    allow_rag_tenant: bool = False
    allow_user_memory: bool = False
    allow_session_context: bool = False
    allow_memory_write: bool = False
