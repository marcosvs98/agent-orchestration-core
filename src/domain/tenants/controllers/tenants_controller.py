from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from domain.tenants.schemas.tenant_operational_summary import (
    TenantOperationalSummaryResponse,
)
from domain.tenants.schemas.tenants import (
    TenantCreate,
    TenantCurrentResponse,
    TenantResponse,
    TenantSettingsResponse,
)
from domain.tenants.services.tenant_summary_service import TenantSummaryService
from domain.tenants.services.tenants_service import TenantsService
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext, get_auth_context


class TenantsController:
    """HTTP controller for tenant resources."""

    def __init__(
        self,
        service: TenantsService,
        summary_service: TenantSummaryService | None = None,
    ) -> None:
        self.service = service
        self.summary_service = summary_service
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
            responses={
                status.HTTP_200_OK: {
                    "description": "Tenant already exists (idempotent by external_id)"
                },
                status.HTTP_201_CREATED: {"description": "Tenant created"},
            },
        )
        self.router.add_api_route(
            "/current",
            self.get_current,
            methods=["GET"],
            response_model=TenantCurrentResponse,
        )
        self.router.add_api_route(
            "/current/summary",
            self.get_current_summary,
            methods=["GET"],
            response_model=TenantOperationalSummaryResponse,
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
    ) -> JSONResponse:
        if "tenants:create" not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")
        response, created = await self.service.create(
            tenant_create=tenant_create, principal_id=auth.principal_id
        )
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return JSONResponse(
            content=response.model_dump(mode="json"),
            status_code=status_code,
        )

    async def get_current(
        self, auth: AuthContext = Depends(get_auth_context)
    ) -> TenantCurrentResponse:
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        return await self.service.get_current(tenant_id=auth.tenant_id)

    async def get_current_summary(
        self, auth: AuthContext = Depends(get_auth_context)
    ) -> TenantOperationalSummaryResponse:
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        if self.summary_service is None:
            raise AuthorizationDeniedException(message="summary_not_available")
        return await self.summary_service.get_current_summary(tenant_id=auth.tenant_id)

    async def get_settings(
        self, auth: AuthContext = Depends(get_auth_context)
    ) -> TenantSettingsResponse:
        if auth.tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        return await self.service.get_settings(tenant_id=auth.tenant_id)
