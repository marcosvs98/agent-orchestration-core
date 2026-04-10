from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from domain.tools.schemas.tools import (
    AgentVersionToolBinding,
    AgentVersionToolBindingCreate,
    Tool,
    ToolConfig,
    ToolConfigCreate,
    ToolImportRequest,
    ToolImportResult,
)
from domain.tools.services.tools_service import ToolsService
from utils.auth import AuthContext, get_auth_context


class ToolsController:
    """HTTP controller for tools."""

    def __init__(self, service: ToolsService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["tools"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/tools/import-tools",
            self.import_tool,
            methods=["POST"],
            response_model=ToolImportResult,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/tools",
            self.list_tools,
            methods=["GET"],
            response_model=list[Tool],
        )
        r(
            "/tool-configs",
            self.list_tool_configs,
            methods=["GET"],
            response_model=list[ToolConfig],
        )
        r(
            "/tool-configs",
            self.create_tool_config,
            methods=["POST"],
            response_model=ToolConfig,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/tool-configs/{tool_config_id}:publish",
            self.publish_tool_config,
            methods=["POST"],
            response_model=ToolConfig,
        )
        r(
            "/tool-configs/{tool_config_id}:deprecate",
            self.deprecate_tool_config,
            methods=["POST"],
            response_model=ToolConfig,
        )
        r(
            "/tool-configs/{tool_config_id}:disable",
            self.disable_tool_config,
            methods=["POST"],
            response_model=ToolConfig,
        )
        r(
            "/agent-version-tool-bindings",
            self.create_agent_version_tool_binding,
            methods=["POST"],
            response_model=AgentVersionToolBinding,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/agent-versions/{agent_version_id}/tools",
            self.list_tools_by_agent_version,
            methods=["GET"],
            response_model=list[AgentVersionToolBinding],
        )

    async def import_tool(
        self,
        tool_import_request: ToolImportRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> ToolImportResult:
        return await self.service.import_tool(
            tenant_id=auth.tenant_id,
            tool_import_request=tool_import_request,
            principal_id=auth.principal_id,
        )

    async def list_tools(
        self,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[Tool]:
        return await self.service.list_tools(tenant_id=auth.tenant_id, limit=limit)

    async def list_tool_configs(
        self,
        status_filter: list[str] | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[ToolConfig]:
        return await self.service.list_tool_configs(
            tenant_id=auth.tenant_id, status_filter=status_filter, limit=limit
        )

    async def create_tool_config(
        self,
        tool_config_create: ToolConfigCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> ToolConfig:
        return await self.service.create_tool_config(
            tenant_id=auth.tenant_id,
            tool_config_create=tool_config_create,
            principal_id=auth.principal_id,
        )

    async def create_agent_version_tool_binding(
        self,
        binding_create: AgentVersionToolBindingCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AgentVersionToolBinding:
        return await self.service.create_agent_version_tool_binding(
            tenant_id=auth.tenant_id,
            binding_create=binding_create,
            principal_id=auth.principal_id,
        )

    async def list_tools_by_agent_version(
        self,
        agent_version_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[AgentVersionToolBinding]:
        return await self.service.list_tool_bindings_by_agent_version(
            tenant_id=auth.tenant_id,
            agent_version_id=agent_version_id,
        )

    async def publish_tool_config(
        self,
        tool_config_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> ToolConfig:
        return await self.service.publish_tool_config(
            tenant_id=auth.tenant_id,
            tool_config_id=tool_config_id,
            principal_id=auth.principal_id,
        )

    async def deprecate_tool_config(
        self,
        tool_config_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> ToolConfig:
        return await self.service.deprecate_tool_config(
            tenant_id=auth.tenant_id,
            tool_config_id=tool_config_id,
            principal_id=auth.principal_id,
        )

    async def disable_tool_config(
        self,
        tool_config_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> ToolConfig:
        return await self.service.disable_tool_config(
            tenant_id=auth.tenant_id,
            tool_config_id=tool_config_id,
            principal_id=auth.principal_id,
        )
