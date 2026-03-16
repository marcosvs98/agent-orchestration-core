from __future__ import annotations

from uuid import UUID

from domain.governance.repositories.llm_model_mapping_repository import (
    LLMModelMappingRepository,
)
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from exceptions.service_exceptions import DomainValidationException


class LLMAdminService:
    def __init__(
        self,
        provider_repository: LLMProviderRepository,
        mapping_repository: LLMModelMappingRepository,
        pricing_repository: LLMPricingRepository,
    ) -> None:
        self.provider_repository = provider_repository
        self.mapping_repository = mapping_repository
        self.pricing_repository = pricing_repository

    async def upsert_provider_config(
        self,
        *,
        tenant_id: UUID,
        provider: str,
        base_url: str | None,
        credential_secret_ref: str | None,
        status: str,
        created_by: str,
    ):
        return await self.provider_repository.upsert_config(
            tenant_id=tenant_id,
            provider=provider,
            base_url=base_url,
            credential_secret_ref=credential_secret_ref,
            status=status,
            created_by=created_by,
        )

    async def upsert_model_mapping(
        self,
        *,
        tenant_id: UUID,
        provider: str,
        model_alias: str,
        provider_model: str,
        status: str,
        created_by: str,
    ):
        active_provider = await self.provider_repository.get_active_config(
            tenant_id=tenant_id,
            provider=provider,
        )
        if active_provider is None:
            raise DomainValidationException(message="llm_provider_config_not_active")
        return await self.mapping_repository.upsert_mapping(
            tenant_id=tenant_id,
            provider=provider,
            model_alias=model_alias,
            provider_model=provider_model,
            status=status,
            created_by=created_by,
        )

    async def upsert_pricing(
        self,
        *,
        provider: str,
        provider_model: str,
        unit: str,
        input_cost_per_1k,
        output_cost_per_1k,
        currency: str,
        status: str,
        created_by: str,
    ):
        return await self.pricing_repository.upsert_pricing(
            provider=provider,
            provider_model=provider_model,
            unit=unit,
            input_cost_per_1k=input_cost_per_1k,
            output_cost_per_1k=output_cost_per_1k,
            currency=currency,
            status=status,
            created_by=created_by,
        )
