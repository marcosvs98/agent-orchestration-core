from uuid import UUID

from pydantic import BaseModel


class Tool(BaseModel):
    id: UUID
    name: str | None = None


class ToolCreate(BaseModel):
    name: str | None = None


class ToolImportRequest(BaseModel):
    openapi_url: str
    name: str | None = None


class ToolImportResult(BaseModel):
    imported_count: int
    tools: list[Tool]


class AvailableTool(BaseModel):
    name: str | None
    tool_id: UUID
    tool_config_id: UUID
    summary: str | None = None
    description: str | None = None
    operation_id: str | None = None
    method: str | None = None
    path: str | None = None
    retrieval_score: float | None = None


class ToolConfig(BaseModel):
    id: UUID
    tool_id: UUID
    config: dict[str, object] | None = None
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None
    schema_version: int | None = None


class ToolConfigCreate(BaseModel):
    tool_id: UUID
    source_config_id: UUID | None = None
    config: dict[str, object] | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None
    schema_version: int | None = None


class AgentVersionToolBinding(BaseModel):
    id: UUID
    agent_version_id: UUID
    tool_config_id: UUID


class AgentVersionToolBindingCreate(BaseModel):
    agent_version_id: UUID
    tool_config_id: UUID
