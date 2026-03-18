from fastapi import APIRouter, Depends, Request, status

from domain.governance.schemas.scopes import Scope
from domain.mcp_registry.schemas.mcp_registry import (
    McpServerCreateRequest,
    McpServerCreateResponse,
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
