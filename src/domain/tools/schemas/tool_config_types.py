from typing import TypedDict


class ToolConfigRagScopeActivation(TypedDict, total=False):
    enabled: bool
    filters_override: dict[str, object]


class ToolConfigRagActivation(TypedDict, total=False):
    tenant_knowledge: ToolConfigRagScopeActivation
    user_memory_vector: ToolConfigRagScopeActivation


class ToolConfigConfig(TypedDict, total=False):
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
