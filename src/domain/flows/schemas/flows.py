from uuid import UUID

from pydantic import BaseModel


class Flow(BaseModel):
    id: UUID
    name: str | None = None


class FlowCreate(BaseModel):
    name: str | None = None


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
    ai_task_id: UUID | None = None


class NodeCreate(BaseModel):
    flow_version_id: UUID
    ai_task_id: UUID | None = None


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
