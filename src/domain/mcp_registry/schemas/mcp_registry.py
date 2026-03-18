from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class McpServerToolBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_config_id: UUID
    mcp_name: str
    description: str
    request_schema: dict[str, Any]
    response_schema: dict[str, Any] | None


class McpServerCreateRequest(BaseModel):
    tool_config_ids: list[UUID] = Field(default_factory=list)
    vector_store_ids: list[UUID] = Field(default_factory=list)
    user_prompt_ids: list[UUID] = Field(default_factory=list)
    name: str | None = None


class McpServerCreateResponse(BaseModel):
    endpoint: str
    api_key: str
    mcp_server_id: UUID


class McpBindingState(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    mcp_server_id: UUID
    tool_config_ids: frozenset[UUID]
    vector_store_ids: frozenset[UUID]
    user_prompt_ids: frozenset[UUID]


class McpServerBuildSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    mcp_server_id: UUID
    tools: tuple[McpServerToolBinding, ...]
    vector_store_ids: tuple[UUID, ...]
    prompts: tuple[tuple[UUID, str, str, str], ...]
