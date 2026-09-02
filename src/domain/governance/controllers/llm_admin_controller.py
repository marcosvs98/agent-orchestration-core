from __future__ import annotations

from fastapi import APIRouter, Depends

from domain.governance.schemas.llm_admin import (
    ModelMappingUpsertRequest,
    PricingUpsertRequest,
    ProviderUpsertRequest,
)
from domain.governance.services.llm_admin_service import LLMAdminService
from utils.auth import ADMIN_PRINCIPAL_ID, get_admin_auth


class LLMAdminController:
    def __init__(self, service: LLMAdminService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/admin/llm",
            tags=["llm-admin"],
            dependencies=[Depends(get_admin_auth)],
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

    async def upsert_provider(self, body: ProviderUpsertRequest):
        return await self.service.upsert_provider_config(
            tenant_id=body.tenant_id,
            provider=body.provider,
            base_url=body.base_url,
            credential_secret_ref=body.credential_secret_ref,
            status=body.status,
            created_by=ADMIN_PRINCIPAL_ID,
        )

    async def upsert_model_mapping(self, body: ModelMappingUpsertRequest):
        return await self.service.upsert_model_mapping(
            tenant_id=body.tenant_id,
            provider=body.provider,
            model_alias=body.model_alias,
            provider_model=body.provider_model,
            status=body.status,
            created_by=ADMIN_PRINCIPAL_ID,
        )

    async def upsert_pricing(self, body: PricingUpsertRequest):
        return await self.service.upsert_pricing(
            provider=body.provider,
            provider_model=body.provider_model,
            unit=body.unit,
            input_cost_per_1k=body.input_cost_per_1k,
            output_cost_per_1k=body.output_cost_per_1k,
            currency=body.currency,
            status=body.status,
            created_by=ADMIN_PRINCIPAL_ID,
        )
