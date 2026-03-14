from typing import TypedDict, Any


class OpenAPISpec(TypedDict, total=False):
    title: str | None
    version: str | None
    paths: dict[str, Any]
    schemas: dict[str, Any]
    openapi_version: str | None
    servers: list[dict[str, Any]]
    components: dict[str, Any]


class OpenAPIOperation(TypedDict, total=False):
    path: str
    method: str
    operation_id: str
    summary: str | None
    description: str | None
    examples: list[str]
    request_schema: dict[str, Any]
    response_schema: dict[str, Any]
