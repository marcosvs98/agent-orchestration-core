from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from domain.governance.services.llm_admin_service import LLMAdminService
from utils.auth import AuthContext, get_auth_context


class LLMAdminController:
    def __init__(self, service: LLMAdminService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/admin/llm",
            tags=["llm-admin"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/provider",
            self.upsert_provider,
            methods=["POST"],
        )
        r(
            "/model-mapping",
            self.upsert_model_mapping,
            methods=["POST"],
        )
        r(
            "/pricing",
            self.upsert_pricing,
            methods=["POST"],
        )

    async def upsert_provider(
        self,
        tenant_id: UUID,
        provider: str,
        status: str,
        base_url: str | None = None,
        credential_secret_ref: str | None = None,
        auth: AuthContext = Depends(get_auth_context),
    ):
        return await self.service.upsert_provider_config(
            tenant_id=tenant_id,
            provider=provider,
            base_url=base_url,
            credential_secret_ref=credential_secret_ref,
            status=status,
            created_by=auth.principal_id,
        )

    async def upsert_model_mapping(
        self,
        tenant_id: UUID,
        provider: str,
        model_alias: str,
        provider_model: str,
        status: str = "ACTIVE",
        auth: AuthContext = Depends(get_auth_context),
    ):
        return await self.service.upsert_model_mapping(
            tenant_id=tenant_id,
            provider=provider,
            model_alias=model_alias,
            provider_model=provider_model,
            status=status,
            created_by=auth.principal_id,
        )

    async def upsert_pricing(
        self,
        provider: str,
        provider_model: str,
        unit: str,
        input_cost_per_1k: float,
        output_cost_per_1k: float,
        currency: str = "USD",
        status: str = "ACTIVE",
        auth: AuthContext = Depends(get_auth_context),
    ):
        return await self.service.upsert_pricing(
            provider=provider,
            provider_model=provider_model,
            unit=unit,
            input_cost_per_1k=input_cost_per_1k,
            output_cost_per_1k=output_cost_per_1k,
            currency=currency,
            status=status,
            created_by=auth.principal_id,
        )
