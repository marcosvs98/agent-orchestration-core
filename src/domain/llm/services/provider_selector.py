from __future__ import annotations

from uuid import UUID

from domain.llm.schemas.llm import LLMProviderSelection
from domain.governance.repositories.llm_model_mapping_repository import (
    LLMModelMappingRepository,
)
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from exceptions.service_exceptions import DomainValidationException
from infra.database.models.governance.llm_model_mapping import (
    LLMModelMapping as LLMModelMappingModel,
)
from infra.database.models.governance.llm_pricing import LLMPricing as LLMPricingModel

class LLMProviderSelector:
    def __init__(
        self,
        provider_repository: LLMProviderRepository,
        model_mapping_repository: LLMModelMappingRepository,
        pricing_repository: LLMPricingRepository,
    ) -> None:
        self.provider_repository = provider_repository
        self.model_mapping_repository = model_mapping_repository
        self.pricing_repository = pricing_repository

    async def select(
        self, *, tenant_id: UUID, provider: str, model_alias: str
    ) -> LLMProviderSelection:
        config = await self.provider_repository.get_active_config(
            tenant_id=tenant_id, provider=provider
        )

        if config is None:
            raise DomainValidationException(message="llm_provider_not_active")

        mapping: LLMModelMappingModel = await self.model_mapping_repository.get_active_mapping(
            tenant_id=tenant_id, provider=provider, model_alias=model_alias
        )
        if mapping is None:
            raise DomainValidationException(message="llm_model_mapping_not_found")

        pricing: LLMPricingModel = await self.pricing_repository.get_active_pricing(
            provider=provider, provider_model=mapping.provider_model
        )
        if pricing is None:
            raise DomainValidationException(message="llm_pricing_not_found")

        return LLMProviderSelection(
            provider=provider,
            provider_model=mapping.provider_model,
            base_url=config.base_url,
            credential_secret_ref=config.credential_secret_ref,
        )
