from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from domain.governance.services.llm_admin_service import LLMAdminService
from exceptions.service_exceptions import DomainValidationException


@pytest.mark.asyncio
async def test_upsert_model_mapping_requires_catalog_entry() -> None:
    tenant_id = uuid4()
    ai_repo = AsyncMock()
    ai_repo.get_model_by_name = AsyncMock(return_value=None)
    provider_repo = AsyncMock()
    provider_repo.get_active_config = AsyncMock(
        return_value=object(),
    )
    mapping_repo = AsyncMock()
    service = LLMAdminService(
        ai_repository=ai_repo,
        provider_repository=provider_repo,
        mapping_repository=mapping_repo,
        pricing_repository=AsyncMock(),
    )
    with pytest.raises(DomainValidationException) as exc:
        await service.upsert_model_mapping(
            tenant_id=tenant_id,
            provider="OPENAI",
            model_alias="unknown-model",
            provider_model="x",
            status="ACTIVE",
            created_by="t",
        )
    assert exc.value.message == "model_catalog_entry_required_for_llm_model_mapping"
    mapping_repo.upsert_mapping.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_model_mapping_passes_model_id() -> None:
    tenant_id = uuid4()
    mid = uuid4()
    catalog = SimpleNamespace(model_id=mid, name="gpt-4o-mini")
    ai_repo = AsyncMock()
    ai_repo.get_model_by_name = AsyncMock(return_value=catalog)
    provider_repo = AsyncMock()
    provider_repo.get_active_config = AsyncMock(return_value=object())
    mapping_repo = AsyncMock()
    mapping_repo.upsert_mapping = AsyncMock()
    service = LLMAdminService(
        ai_repository=ai_repo,
        provider_repository=provider_repo,
        mapping_repository=mapping_repo,
        pricing_repository=AsyncMock(),
    )
    await service.upsert_model_mapping(
        tenant_id=tenant_id,
        provider="OPENAI",
        model_alias="gpt-4o-mini",
        provider_model="gpt-4o-mini",
        status="ACTIVE",
        created_by="t",
    )
    mapping_repo.upsert_mapping.assert_awaited_once()
    call = mapping_repo.upsert_mapping.await_args
    assert call.kwargs["model_id"] == mid
    assert call.kwargs["model_alias"] == "gpt-4o-mini"
