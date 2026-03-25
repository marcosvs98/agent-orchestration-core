from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from domain.governance.schemas.scopes import Scope
from domain.mcp_registry.schemas.mcp_registry import (
    McpServerCreateRequest,
    McpServerCreateResponse,
    McpServerDetail,
    McpServerSummary,
)
from domain.mcp_registry.services.mcp_registry_service import McpRegistryService
from exceptions.service_exceptions import AuthorizationDeniedException
from settings import PUBLIC_BASE_URL
from utils.auth import AuthContext, get_auth_context


class McpRegistryController:
    def __init__(self, service: McpRegistryService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1/tenants",
            tags=["mcp-registry"],
            dependencies=[Depends(get_auth_context)],
        )
        self.router.add_api_route(
            "/mcp-servers",
            self.create_mcp_server,
            methods=["POST"],
            response_model=McpServerCreateResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/mcp-servers",
            self.list_mcp_servers,
            methods=["GET"],
            response_model=list[McpServerSummary],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/mcp-servers/{mcp_server_id}",
            self.get_mcp_server,
            methods=["GET"],
            response_model=McpServerDetail,
            status_code=status.HTTP_200_OK,
        )

    async def create_mcp_server(
        self,
        body: McpServerCreateRequest,
        request: Request,
        auth: AuthContext = Depends(get_auth_context),
    ) -> McpServerCreateResponse:
        if Scope.McpServersCreate.value not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        eb = (
            PUBLIC_BASE_URL.strip()
            if PUBLIC_BASE_URL.strip()
            else str(request.base_url).rstrip("/")
        )
        return await self.service.create_server(
            tenant_id=auth.tenant_id,
            body=body,
            endpoint_base=eb,
        )

    async def list_mcp_servers(
        self,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[McpServerSummary]:
        if Scope.McpServersList.value not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        return await self.service.list_servers(tenant_id=auth.tenant_id)

    async def get_mcp_server(
        self,
        mcp_server_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> McpServerDetail:
        if Scope.McpServersGet.value not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        return await self.service.get_server(
            tenant_id=auth.tenant_id,
            mcp_server_id=mcp_server_id,
        )
