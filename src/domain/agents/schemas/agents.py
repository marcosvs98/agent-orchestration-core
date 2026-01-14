from uuid import UUID

from pydantic import BaseModel


class Agent(BaseModel):
    id: UUID
    name: str | None = None


class AgentCreate(BaseModel):
    name: str | None = None


class AgentVersion(BaseModel):
    id: UUID
    agent_id: UUID
    description: str | None = None
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None
    supported_tool_schema_version: int | None = None
    supported_tool_config_hash_prefix: str | None = None


class AgentVersionCreate(BaseModel):
    description: str | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None
    supported_tool_schema_version: int | None = None
    supported_tool_config_hash_prefix: str | None = None


class NodeAgentBinding(BaseModel):
    id: UUID
    node_id: UUID
    agent_version_id: UUID


class NodeAgentBindingCreate(BaseModel):
    node_id: UUID
    agent_version_id: UUID
