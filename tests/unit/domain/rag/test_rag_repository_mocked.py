from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.rag.repositories.rag_repository import RagRepository
from infra.database.models.rag.rag_chunking_rule import (
    RagChunkingRule as RagChunkingRuleModel,
)
from infra.database.models.rag.rag_config import RagConfig as RagConfigModel
from infra.database.models.rag.rag_document import RagDocument as RagDocumentModel
from infra.database.models.rag.rag_query_cache import (
    RagQueryCache as RagQueryCacheModel,
)
from infra.database.models.rag.vector_store import VectorStore as VectorStoreModel

from tests.unit.domain.rag.rag_repository_doubles import (
    async_session_double,
    bind_rag_session,
    execute_result_scalar_one,
    execute_result_scalars_all,
)


@pytest.mark.asyncio
async def test_get_vector_store_returns_row(rag_repo: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock(spec=VectorStoreModel)
    session.execute = AsyncMock(return_value=execute_result_scalar_one(row))
    bind_rag_session(rag_repo, session)
    out = await rag_repo.get_vector_store(uuid4(), tenant_id=uuid4())
    assert out is row


@pytest.mark.asyncio
async def test_get_rag_config_returns_row(rag_repo: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock(spec=RagConfigModel)
    session.execute = AsyncMock(return_value=execute_result_scalar_one(row))
    bind_rag_session(rag_repo, session)
    assert await rag_repo.get_rag_config(uuid4()) is row


@pytest.mark.asyncio
async def test_get_document_by_id_returns_row(rag_repo: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock(spec=RagDocumentModel)
    session.execute = AsyncMock(return_value=execute_result_scalar_one(row))
    bind_rag_session(rag_repo, session)
    assert await rag_repo.get_document_by_id(document_id=uuid4()) is row


@pytest.mark.asyncio
async def test_get_query_cache_returns_none(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.execute = AsyncMock(return_value=execute_result_scalar_one(None))
    bind_rag_session(rag_repo, session)
    assert (
        await rag_repo.get_query_cache(
            tenant_id=uuid4(),
            vector_store_id=uuid4(),
            vector_store_version=1,
            contract_hash="h",
            query_hash="q",
        )
        is None
    )


@pytest.mark.asyncio
async def test_invalidate_query_cache_contract_runs(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.execute = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.invalidate_query_cache_contract(
        tenant_id=uuid4(),
        vector_store_id=uuid4(),
        contract_hash="h",
    )
    session.execute.assert_awaited()


@pytest.mark.asyncio
async def test_list_vector_stores(rag_repo: RagRepository) -> None:
    session = async_session_double()
    v1 = MagicMock(spec=VectorStoreModel)
    session.execute = AsyncMock(return_value=execute_result_scalars_all([v1]))
    bind_rag_session(rag_repo, session)
    assert await rag_repo.list_vector_stores(tenant_id=uuid4()) == [v1]


@pytest.mark.asyncio
async def test_get_chunking_rule(rag_repo: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock(spec=RagChunkingRuleModel)
    session.execute = AsyncMock(return_value=execute_result_scalar_one(row))
    bind_rag_session(rag_repo, session)
    out = await rag_repo.get_chunking_rule(
        tenant_id=uuid4(), rag_chunking_rule_id=uuid4()
    )
    assert out is row


@pytest.mark.asyncio
async def test_list_chunking_rules(rag_repo: RagRepository) -> None:
    session = async_session_double()
    r1 = MagicMock(spec=RagChunkingRuleModel)
    session.execute = AsyncMock(return_value=execute_result_scalars_all([r1]))
    bind_rag_session(rag_repo, session)
    assert await rag_repo.list_chunking_rules(tenant_id=uuid4()) == [r1]


@pytest.mark.asyncio
async def test_get_published_rag_config_id_for_vector_store(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    cid = uuid4()
    session.execute = AsyncMock(return_value=execute_result_scalar_one(cid))
    bind_rag_session(rag_repo, session)
    out = await rag_repo.get_published_rag_config_id_for_vector_store(
        tenant_id=uuid4(), vector_store_id=uuid4()
    )
    assert out == cid


@pytest.mark.asyncio
async def test_save_query_cache(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.add = MagicMock()
    session.commit = AsyncMock()
    entry = MagicMock(spec=RagQueryCacheModel)
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    out = await rag_repo.save_query_cache(cache_entry=entry)
    session.add.assert_called_once_with(entry)
    assert out is entry


@pytest.mark.asyncio
async def test_invalidate_query_cache_vector_store(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.execute = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.invalidate_query_cache_vector_store(
        tenant_id=uuid4(), vector_store_id=uuid4()
    )
    session.execute.assert_awaited()
