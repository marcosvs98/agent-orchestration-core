from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from domain.tools.repositories.tools_repository import ToolsRepository

_UNSAFE_FUNCTION_NAME = re.compile(r"[^a-zA-Z0-9_-]")


def normalize_tool_function_name(name: str | None, tool_config_id: UUID) -> str:
    """Callable identifier for one tool config, stable across runs.

    Same shape the tenant MCP server exposes, so a tool keeps one name whether the model reaches
    it through MCP or through an agent run.
    """

    base = _UNSAFE_FUNCTION_NAME.sub("_", (name or "").strip())
    if not base:
        base = f"tool_{str(tool_config_id)[:8]}"
    return base[:64]


def tool_request_schema(config: dict) -> dict:
    request_schema = config.get("request_schema")
    if isinstance(request_schema, dict) and request_schema.get("type") == "object":
        return dict(request_schema)
    if isinstance(request_schema, dict) and "properties" in request_schema:
        return {"type": "object", **request_schema}
    return {"type": "object", "properties": {}, "additionalProperties": True}


class AgentToolBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    function_name: str
    tool_id: UUID
    tool_config_id: UUID
    tool_name: str
    description: str
    request_schema: dict


class AgentToolCatalog:
    """The tools an agent version is bound to, as callable function definitions."""

    def __init__(self, tools_repository: ToolsRepository) -> None:
        self.tools_repository = tools_repository

    async def list_agent_version_tools(
        self, *, tenant_id: UUID, agent_version_id: UUID
    ) -> list[AgentToolBinding]:
        bindings = await self.tools_repository.list_tool_bindings_by_agent_version_id(
            tenant_id=tenant_id, agent_version_id=agent_version_id
        )
        if not bindings:
            return []
        rows = await self.tools_repository.list_published_tool_configs_with_tools_by_config_ids(
            tenant_id=tenant_id,
            tool_config_ids=[binding.tool_config_id for binding in bindings],
        )
        catalog: list[AgentToolBinding] = []
        used_names: set[str] = set()
        for tool_config, tool in rows:
            config = tool_config.config or {}
            function_name = normalize_tool_function_name(tool.name, tool_config.tool_config_id)
            if function_name in used_names:
                suffix = str(tool_config.tool_config_id).replace("-", "")[:8]
                function_name = f"{function_name}_{suffix}"
            used_names.add(function_name)
            catalog.append(
                AgentToolBinding(
                    function_name=function_name,
                    tool_id=tool_config.tool_id,
                    tool_config_id=tool_config.tool_config_id,
                    tool_name=str(tool.name or function_name),
                    description=str(
                        config.get("description") or config.get("summary") or ""
                    ).strip(),
                    request_schema=tool_request_schema(config),
                )
            )
        return catalog
