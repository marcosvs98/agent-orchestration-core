from fastapi import APIRouter, Depends

from domain.auth.schemas.auth import TenantTokenRequest, TenantTokenResponse
from domain.auth.services.auth_service import AuthService
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext, get_auth_context
from domain.governance.schemas.scopes import Scope


class AuthController:
    """HTTP controller for auth endpoints."""

    def __init__(self, service: AuthService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1/auth",
            tags=["auth"],
            dependencies=[Depends(get_auth_context)],
        )
        self.router.add_api_route(
            "/tenant-token",
            self.issue_tenant_token,
            methods=["POST"],
            response_model=TenantTokenResponse,
        )

    async def issue_tenant_token(
        self,
        body: TenantTokenRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> TenantTokenResponse:
        """Issue a JWT for the given tenant. Requires tenants:create scope."""
        if Scope.TenantsCreate not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        return await self.service.issue_tenant_token(
            tenant_id=body.tenant_id,
            auth=auth,
        )
