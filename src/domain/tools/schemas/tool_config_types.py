from typing import Any, TypedDict

from pydantic import BaseModel


class ToolConfigRagScopeActivation(TypedDict, total=False):
    enabled: bool
    filters_override: dict[str, object]


class ToolConfigRagActivation(TypedDict, total=False):
    tenant_knowledge: ToolConfigRagScopeActivation
    user_memory_vector: ToolConfigRagScopeActivation


class ToolConfigConfig(TypedDict, total=False):
    base_url: str
    url: str
    path: str
    method: str
    request_schema: dict
    response_schema: dict
    operation_id: str
    summary: str
    description: str
    examples: list[str]
    rag_activation: ToolConfigRagActivation
    headers: dict[str, Any]


class ToolConfigRagScopeActivationSchema(BaseModel):
    """Pydantic schema for RAG scope activation at API boundary."""

    enabled: bool | None = None
    filters_override: dict[str, object] | None = None


class ToolConfigRagActivationSchema(BaseModel):
    """Pydantic schema for RAG activation at API boundary."""

    tenant_knowledge: ToolConfigRagScopeActivationSchema | None = None
    user_memory_vector: ToolConfigRagScopeActivationSchema | None = None


class ToolConfigConfigSchema(BaseModel):
    """Pydantic schema for tool config at API boundary. Used in POST /tool-configs."""

    base_url: str | None = None
    url: str | None = None
    path: str | None = None
    method: str | None = None
    request_schema: dict[str, object] | None = None
    response_schema: dict[str, object] | None = None
    operation_id: str | None = None
    summary: str | None = None
    description: str | None = None
    examples: list[str] | None = None
    rag_activation: ToolConfigRagActivationSchema | None = None
    headers: dict[str, object] | None = None
