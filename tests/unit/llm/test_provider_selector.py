import contextlib
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from domain.governance.repositories.llm_model_mapping_repository import LLMModelMappingRepository
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from domain.llm.services.provider_selector import LLMProviderSelector
from exceptions.service_exceptions import DomainValidationException


class _Row:
    """Stand-in for an ORM row: attribute access plus the `to_dict()` the tracer calls."""

    def __init__(self, **fields: Any) -> None:
        self.__dict__.update(fields)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class _ProviderRepo(LLMProviderRepository):
    def __init__(self) -> None:  # type: ignore[call-arg]
        self.config = None

    async def get_active_config(self, *, tenant_id, provider):
        return _Row(
            tenant_id=tenant_id,
            provider=provider,
            base_url="url",
            credential_secret_ref="ref",
        )


class _MappingRepo(LLMModelMappingRepository):
    def __init__(self) -> None:  # type: ignore[call-arg]
        self.mapping = None

    async def get_active_mapping(self, *, tenant_id, provider, model_alias):
        return _Row(
            tenant_id=tenant_id,
            provider=provider,
            model_alias=model_alias,
            provider_model="gpt-4o-mini",
        )


class _PricingRepo(LLMPricingRepository):
    def __init__(self) -> None:  # type: ignore[call-arg]
        self.pricing = None

    async def get_active_pricing(self, *, provider, provider_model):
        return _Row(provider=provider, provider_model=provider_model)


class _FakeTracer:
    @contextlib.contextmanager
    def observe(self, **_):
        yield MagicMock()


def _selector(mapping_repo: LLMModelMappingRepository | None = None) -> LLMProviderSelector:
    return LLMProviderSelector(
        _ProviderRepo(),
        mapping_repo or _MappingRepo(),
        _PricingRepo(),
        _FakeTracer(),
    )


@pytest.mark.asyncio
async def test_provider_selector_happy_path():
    sel = await _selector().select(
        tenant_id=uuid.uuid4(), provider="OPENAI", model_alias="text-small"
    )

    assert sel.provider_model == "gpt-4o-mini"
    assert sel.base_url == "url"
    assert sel.credential_secret_ref == "ref"


class _EmptyMappingRepo(_MappingRepo):
    async def get_active_mapping(self, *, tenant_id, provider, model_alias):
        return None


@pytest.mark.asyncio
async def test_provider_selector_raises_if_mapping_missing():
    with pytest.raises(DomainValidationException, match="llm_model_mapping_not_found"):
        await _selector(_EmptyMappingRepo()).select(
            tenant_id=uuid.uuid4(), provider="OPENAI", model_alias="text-small"
        )
