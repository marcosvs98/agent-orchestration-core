import uuid

import pytest

from domain.governance.repositories.llm_model_mapping_repository import LLMModelMappingRepository
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from domain.llm.services.provider_selector import LLMProviderSelector
from exceptions.service_exceptions import DomainValidationException


class _ProviderRepo(LLMProviderRepository):
    def __init__(self) -> None:  # type: ignore[call-arg]
        self.config = None

    async def get_active_config(self, *, tenant_id, provider):
        return type(
            "Cfg",
            (),
            {"tenant_id": tenant_id, "provider": provider, "base_url": "url", "credential_secret_ref": "ref"},
        )()


class _MappingRepo(LLMModelMappingRepository):
    def __init__(self) -> None:  # type: ignore[call-arg]
        self.mapping = None

    async def get_active_mapping(self, *, tenant_id, provider, model_alias):
        return type(
            "Mapping",
            (),
            {"tenant_id": tenant_id, "provider": provider, "model_alias": model_alias, "provider_model": "gpt-4o-mini"},
        )()


class _PricingRepo(LLMPricingRepository):
    def __init__(self) -> None:  # type: ignore[call-arg]
        self.pricing = None

    async def get_active_pricing(self, *, provider, provider_model):
        return type("Pricing", (), {"provider": provider, "provider_model": provider_model})()


@pytest.mark.asyncio
async def test_provider_selector_happy_path():
    selector = LLMProviderSelector(_ProviderRepo(), _MappingRepo(), _PricingRepo())
    sel = await selector.select(tenant_id=uuid.uuid4(), provider="OPENAI", model_alias="text-small")
    assert sel.provider_model == "gpt-4o-mini"


class _EmptyMappingRepo(_MappingRepo):
    async def get_active_mapping(self, *, tenant_id, provider, model_alias):
        return None


@pytest.mark.asyncio
async def test_provider_selector_raises_if_mapping_missing():
    selector = LLMProviderSelector(_ProviderRepo(), _EmptyMappingRepo(), _PricingRepo())
    with pytest.raises(DomainValidationException):
        await selector.select(tenant_id=uuid.uuid4(), provider="OPENAI", model_alias="text-small")
