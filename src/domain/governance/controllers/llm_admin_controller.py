from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from domain.governance.services.llm_admin_service import LLMAdminService
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from domain.governance.repositories.llm_model_mapping_repository import (
    LLMModelMappingRepository,
)
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from infra.database import get_db


router = APIRouter(prefix="/admin/llm", tags=["llm-admin"])


def get_service(db=Depends(get_db)) -> LLMAdminService:
    return LLMAdminService(
        LLMProviderRepository(db),
        LLMModelMappingRepository(db),
        LLMPricingRepository(db),
    )


@router.post("/provider")
async def upsert_provider(
    tenant_id: UUID,
    provider: str,
    status: str,
    base_url: str | None = None,
    credential_secret_ref: str | None = None,
    created_by: str = "admin",
    service: LLMAdminService = Depends(get_service),
):
    return await service.upsert_provider_config(
        tenant_id=tenant_id,
        provider=provider,
        base_url=base_url,
        credential_secret_ref=credential_secret_ref,
        status=status,
        created_by=created_by,
    )


@router.post("/model-mapping")
async def upsert_model_mapping(
    tenant_id: UUID,
    provider: str,
    model_alias: str,
    provider_model: str,
    status: str = "ACTIVE",
    created_by: str = "admin",
    service: LLMAdminService = Depends(get_service),
):
    return await service.upsert_model_mapping(
        tenant_id=tenant_id,
        provider=provider,
        model_alias=model_alias,
        provider_model=provider_model,
        status=status,
        created_by=created_by,
    )


@router.post("/pricing")
async def upsert_pricing(
    provider: str,
    provider_model: str,
    unit: str,
    input_cost_per_1k: float,
    output_cost_per_1k: float,
    currency: str = "USD",
    status: str = "ACTIVE",
    created_by: str = "admin",
    service: LLMAdminService = Depends(get_service),
):
    return await service.upsert_pricing(
        provider=provider,
        provider_model=provider_model,
        unit=unit,
        input_cost_per_1k=input_cost_per_1k,
        output_cost_per_1k=output_cost_per_1k,
        currency=currency,
        status=status,
        created_by=created_by,
    )
