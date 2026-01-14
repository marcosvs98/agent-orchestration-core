from fastapi import APIRouter, Depends, status

from domain.tools.schemas.tools import (
    AgentVersionToolBinding,
    AgentVersionToolBindingCreate,
    Tool,
    ToolConfig,
    ToolConfigCreate,
    ToolCreate,
    ToolImportRequest,
)
from domain.tools.services.tools_service import ToolsService
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import MethodNotAllowedPlaceholderException
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
        r("/tools/import-openapi", self.import_tool, methods=["POST"], response_model=Tool, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/tools", self.list_tools, methods=["GET"], response_model=list[Tool], responses=self._resp405())
        r("/tool-configs", self.list_tool_configs, methods=["GET"], response_model=list[ToolConfig], responses=self._resp405())
        r("/tool-configs", self.create_tool_config, methods=["POST"], response_model=ToolConfig, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/tool-configs/{tool_config_id}:publish", self.publish_tool_config, methods=["POST"], response_model=ToolConfig, responses=self._resp405())
        r("/tool-configs/{tool_config_id}:deprecate", self.deprecate_tool_config, methods=["POST"], response_model=ToolConfig, responses=self._resp405())
        r("/tool-configs/{tool_config_id}:disable", self.disable_tool_config, methods=["POST"], response_model=ToolConfig, responses=self._resp405())
        r("/agent-version-tool-bindings", self.create_agent_version_tool_binding, methods=["POST"], response_model=AgentVersionToolBinding, status_code=status.HTTP_201_CREATED, responses=self._resp405())

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def import_tool(self, __: ToolImportRequest, _: AuthContext = Depends(get_auth_context)) -> Tool:
        raise MethodNotAllowedPlaceholderException()

    async def list_tools(self, _: AuthContext = Depends(get_auth_context)) -> list[Tool]:
        raise MethodNotAllowedPlaceholderException()

    async def list_tool_configs(
        self, status_filter: list[str] | None = None, _: AuthContext = Depends(get_auth_context)
    ) -> list[ToolConfig]:
        raise MethodNotAllowedPlaceholderException()

    async def create_tool_config(self, __: ToolConfigCreate, _: AuthContext = Depends(get_auth_context)) -> ToolConfig:
        raise MethodNotAllowedPlaceholderException()

    async def create_agent_version_tool_binding(
        self,
        __: AgentVersionToolBindingCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> AgentVersionToolBinding:
        raise MethodNotAllowedPlaceholderException()

    async def publish_tool_config(
        self, tool_config_id: str, _: AuthContext = Depends(get_auth_context)
    ) -> ToolConfig:
        raise MethodNotAllowedPlaceholderException()

    async def deprecate_tool_config(
        self, tool_config_id: str, _: AuthContext = Depends(get_auth_context)
    ) -> ToolConfig:
        raise MethodNotAllowedPlaceholderException()

    async def disable_tool_config(
        self, tool_config_id: str, _: AuthContext = Depends(get_auth_context)
    ) -> ToolConfig:
        raise MethodNotAllowedPlaceholderException()
