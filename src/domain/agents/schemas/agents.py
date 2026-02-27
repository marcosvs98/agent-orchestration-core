from typing import Literal

from pydantic import BaseModel, Field
from uuid import UUID


class Agent(BaseModel):
    id: UUID
    name: str | None = None


class AgentCreate(BaseModel):
    name: str | None = None


class PersonaConfig(BaseModel):
    language: str = "pt_BR"
    tone: Literal["professional", "friendly", "neutral"] = "professional"
    style: Literal["concise", "detailed"] = "concise"
    rules: list[str] = Field(default_factory=list)
    max_response_length: int = 500


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
    persona_config: PersonaConfig | None = None
    system_prompt: str | None = None


class AgentVersionCreate(BaseModel):
    source_version_id: UUID | None = None
    description: str | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None
    supported_tool_schema_version: int | None = None
    supported_tool_config_hash_prefix: str | None = None
    persona_config: PersonaConfig | None = None
    system_prompt: str | None = None


class NodeAgentBinding(BaseModel):
    id: UUID
    node_id: UUID
    agent_version_id: UUID


class NodeAgentBindingCreate(BaseModel):
    node_id: UUID
    agent_version_id: UUID
