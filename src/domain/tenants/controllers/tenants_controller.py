from fastapi import APIRouter, Depends, status

from domain.tenants.schemas.tenants import (
    TenantCreate,
    TenantCurrentResponse,
    TenantResponse,
    TenantSettingsResponse,
)
from domain.tenants.services.tenants_service import TenantsService
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext, get_auth_context


class TenantsController:
    """HTTP controller for tenant resources."""

    def __init__(self, service: TenantsService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1/tenants",
            tags=["tenants"],
            dependencies=[Depends(get_auth_context)],
        )
        self.router.add_api_route(
            "",
            self.create,
            methods=["POST"],
            response_model=TenantResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/current",
            self.get_current,
            methods=["GET"],
            response_model=TenantCurrentResponse,
        )
        self.router.add_api_route(
            "/current/settings",
            self.get_settings,
            methods=["GET"],
            response_model=TenantSettingsResponse,
        )

    async def create(
        self,
        tenant_create: TenantCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> TenantResponse:
        if "tenants:create" not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        return await self.service.create(
            tenant_create=tenant_create, principal_id=auth.principal_id
        )

    async def get_current(
        self, auth: AuthContext = Depends(get_auth_context)
    ) -> TenantCurrentResponse:
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        return await self.service.get_current(tenant_id=auth.tenant_id)

    async def get_settings(
        self, auth: AuthContext = Depends(get_auth_context)
    ) -> TenantSettingsResponse:
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        return await self.service.get_settings(tenant_id=auth.tenant_id)
