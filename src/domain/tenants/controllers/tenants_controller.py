from fastapi import APIRouter, Depends, status

from domain.tenants.schemas.tenants import TenantCurrentResponse, TenantSettingsResponse
from domain.tenants.services.tenants_service import TenantsService
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import MethodNotAllowedPlaceholderException
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
            "/current",
            self.get_current,
            methods=["GET"],
            response_model=TenantCurrentResponse,
            responses={status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}},
        )
        self.router.add_api_route(
            "/current/settings",
            self.get_settings,
            methods=["GET"],
            response_model=TenantSettingsResponse,
            responses={status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}},
        )

    async def get_current(self, _: AuthContext = Depends(get_auth_context)) -> TenantCurrentResponse:
        raise MethodNotAllowedPlaceholderException()

    async def get_settings(self, _: AuthContext = Depends(get_auth_context)) -> TenantSettingsResponse:
        raise MethodNotAllowedPlaceholderException()
