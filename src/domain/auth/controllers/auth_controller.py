from uuid import UUID

from fastapi import APIRouter, Depends, status

from domain.auth.schemas.auth import (
    InboundServiceKeyCreateRequest,
    InboundServiceKeyCreateResponse,
    InboundServiceKeyRevokeRequest,
    TenantTokenRequest,
    TenantTokenResponse,
)
from domain.auth.services.auth_service import AuthService
from exceptions.service_exceptions import (
    AuthorizationDeniedException,
    RouterValidationException,
)
from utils.auth import AuthContext, get_auth_context, get_tenant_token_m2m_auth
from domain.governance.schemas.scopes import Scope


class AuthController:
    def __init__(self, service: AuthService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1/auth",
            tags=["auth"],
        )
        self.router.add_api_route(
            "/tenant-token",
            self.issue_tenant_token,
            methods=["POST"],
            response_model=TenantTokenResponse,
        )
        self.router.add_api_route(
            "/inbound-service-keys",
            self.create_inbound_service_key,
            methods=["POST"],
            response_model=InboundServiceKeyCreateResponse,
            dependencies=[Depends(get_auth_context)],
        )
        self.router.add_api_route(
            "/inbound-service-keys/{inbound_service_key_id}/revoke",
            self.revoke_inbound_service_key,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
            dependencies=[Depends(get_auth_context)],
        )

    async def issue_tenant_token(
        self,
        body: TenantTokenRequest,
        auth: AuthContext = Depends(get_tenant_token_m2m_auth),
    ) -> TenantTokenResponse:
        if Scope.TenantsCreate not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        tid = body.tenant_id if body.tenant_id is not None else auth.tenant_id
        if tid is None:
            raise RouterValidationException(message="tenant_id_required")
        return await self.service.issue_tenant_token(tenant_id=tid, auth=auth)

    async def create_inbound_service_key(
        self,
        body: InboundServiceKeyCreateRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> InboundServiceKeyCreateResponse:
        if Scope.TenantsCreate not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        if auth.tenant_id is not None and auth.tenant_id != body.tenant_id:
            raise AuthorizationDeniedException(message="tenant_scope_mismatch")
        kid, tid, secret = await self.service.create_inbound_service_key(
            tenant_id=body.tenant_id,
            auth=auth,
        )
        return InboundServiceKeyCreateResponse(
            inbound_service_key_id=kid,
            tenant_id=tid,
            secret=secret,
        )

    async def revoke_inbound_service_key(
        self,
        inbound_service_key_id: UUID,
        body: InboundServiceKeyRevokeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        if Scope.TenantsCreate not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        if auth.tenant_id is not None and auth.tenant_id != body.tenant_id:
            raise AuthorizationDeniedException(message="tenant_scope_mismatch")
        await self.service.revoke_inbound_service_key(
            inbound_service_key_id=inbound_service_key_id,
            tenant_id=body.tenant_id,
            auth=auth,
        )
