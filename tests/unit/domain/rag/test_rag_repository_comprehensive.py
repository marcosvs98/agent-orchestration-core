"""Broad mocked coverage for RagRepository (RAG delivery paths)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from domain.common.schemas.versioning import VersionStatus
from domain.governance.schemas.rag_policy import RagIngestQuotas
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.embedding_job import EmbeddingStatus
from exceptions.service_exceptions import DomainValidationException, NotFoundServiceException

from tests.unit.domain.rag.rag_repository_doubles import (
    async_session_double,
    bind_rag_session,
    nested_transaction_context,
)


@pytest.mark.asyncio
async def test_get_vector_store_no_tenant_filter(rag_repo: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    assert await rag_repo.get_vector_store(uuid4()) is row


@pytest.mark.asyncio
async def test_list_vector_stores_no_tracer(rag_repo_no_tracer: RagRepository) -> None:
    session = async_session_double()
    v1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [v1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    out = await rag_repo_no_tracer.list_vector_stores(tenant_id=uuid4())
    assert out == [v1]


@pytest.mark.asyncio
async def test_create_vector_store(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    tid = uuid4()
    out = await rag_repo.create_vector_store(
        tenant_id=tid,
        name="vs",
        embedding_model="m",
        embedding_dimension=1536,
    )
    session.add.assert_called_once()
    assert out is session.add.call_args[0][0]


@pytest.mark.asyncio
async def test_get_rag_config_cache_hit_dict(
    rag_repo: RagRepository,
) -> None:
    cfg = MagicMock()
    with patch(
        "domain.rag.repositories.rag_repository.RagConfigModel.from_dict",
        return_value=cfg,
    ):
        rag_repo.cache_adapter.get = AsyncMock(return_value={"id": "x"})
        out = await rag_repo.get_rag_config(uuid4())
        assert out is cfg


@pytest.mark.asyncio
async def test_get_rag_config_db_sets_cache(rag_repo: RagRepository) -> None:
    row = MagicMock()
    row.to_dict.return_value = {"k": 1}
    session = async_session_double()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    out = await rag_repo.get_rag_config(uuid4())
    assert out is row
    rag_repo.cache_adapter.set.assert_awaited()


@pytest.mark.asyncio
async def test_get_rag_config_no_tracer(rag_repo_no_tracer: RagRepository) -> None:
    row = MagicMock()
    row.to_dict.return_value = {}
    session = async_session_double()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert await rag_repo_no_tracer.get_rag_config(uuid4()) is row


@pytest.mark.asyncio
async def test_update_rag_config_vector_store(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.update_rag_config_vector_store(
        rag_config_id=uuid4(), tenant_id=uuid4(), vector_store_id=uuid4()
    )
    rag_repo.cache_adapter.delete.assert_awaited()


@pytest.mark.asyncio
async def test_set_vector_store_active(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.set_vector_store_active(
        vector_store_id=uuid4(), tenant_id=uuid4(), active=False
    )


@pytest.mark.asyncio
async def test_create_chunking_rule(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    out = await rag_repo.create_chunking_rule(
        tenant_id=uuid4(),
        name="n",
        status="active",
        strategy="fixed",
        params={},
    )
    assert out is session.add.call_args[0][0]


@pytest.mark.asyncio
async def test_update_chunking_rule_miss(rag_repo: RagRepository) -> None:
    session = async_session_double()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    assert (
        await rag_repo.update_chunking_rule(
            tenant_id=uuid4(), rag_chunking_rule_id=uuid4(), name="x"
        )
        is None
    )


@pytest.mark.asyncio
async def test_update_chunking_rule_updates(rag_repo: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    out = await rag_repo.update_chunking_rule(
        tenant_id=uuid4(),
        rag_chunking_rule_id=uuid4(),
        name="new",
        status="s",
        strategy="st",
        params={"a": 1},
    )
    assert out is row


@pytest.mark.asyncio
async def test_list_rag_configs_with_status_filter(rag_repo: RagRepository) -> None:
    session = async_session_double()
    c1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [c1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    out = await rag_repo.list_rag_configs(
        tenant_id=uuid4(), status_filter=["draft"], limit=10
    )
    assert out == [c1]


@pytest.mark.asyncio
async def test_list_rag_configs_no_tracer(rag_repo_no_tracer: RagRepository) -> None:
    session = async_session_double()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert (
        await rag_repo_no_tracer.list_rag_configs(tenant_id=uuid4(), limit=5) == []
    )


@pytest.mark.asyncio
async def test_create_rag_config_validation_missing_chunking(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    last_res = MagicMock()
    last_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=last_res)
    bind_rag_session(rag_repo, session)
    with pytest.raises(DomainValidationException):
        await rag_repo.create_rag_config(
            tenant_id=uuid4(),
            vector_store_id=uuid4(),
            corpus_kind="k",
            created_by="u",
        )


@pytest.mark.asyncio
async def test_create_rag_config_source_not_found(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    src_res = MagicMock()
    src_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=src_res)
    bind_rag_session(rag_repo, session)
    with pytest.raises(NotFoundServiceException):
        await rag_repo.create_rag_config(
            tenant_id=uuid4(),
            source_version_id=uuid4(),
            vector_store_id=uuid4(),
            corpus_kind="k",
            chunking_rule_id=uuid4(),
            version_major=1,
            version_minor=0,
            version_patch=0,
            created_by="u",
        )


@pytest.mark.asyncio
async def test_create_rag_config_chunking_rule_missing(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    last_res = MagicMock()
    last = MagicMock()
    last.version_major = 1
    last.version_minor = 0
    last.version_patch = 0
    last_res.scalar_one_or_none = MagicMock(return_value=last)
    cr_res = MagicMock()
    cr_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(side_effect=[last_res, cr_res])
    bind_rag_session(rag_repo, session)
    with pytest.raises(NotFoundServiceException):
        await rag_repo.create_rag_config(
            tenant_id=uuid4(),
            vector_store_id=uuid4(),
            chunking_rule_id=uuid4(),
            corpus_kind="k",
            created_by="u",
        )


@pytest.mark.asyncio
async def test_create_rag_config_success_from_scratch(
    rag_repo: RagRepository,
) -> None:
    tid, vid, cid = uuid4(), uuid4(), uuid4()
    session = async_session_double()
    cr_row = MagicMock()
    cr_res = MagicMock()
    cr_res.scalar_one_or_none = MagicMock(return_value=cr_row)
    # With explicit version tuple, create_rag_config only queries chunking rule (no last_version query).
    session.execute = AsyncMock(return_value=cr_res)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    out = await rag_repo.create_rag_config(
        tenant_id=tid,
        vector_store_id=vid,
        chunking_rule_id=cid,
        corpus_kind="TENANT_KNOWLEDGE",
        version_major=1,
        version_minor=0,
        version_patch=0,
        created_by="u",
    )
    session.add.assert_called_once()
    assert out is session.add.call_args[0][0]


@pytest.mark.asyncio
async def test_set_rag_config_status_not_found(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    with pytest.raises(NotFoundServiceException):
        await rag_repo.set_rag_config_status(
            rag_config_id=uuid4(), status=VersionStatus.PUBLISHED
        )


@pytest.mark.asyncio
async def test_set_rag_config_status_ok(rag_repo: RagRepository) -> None:
    session = async_session_double()
    inst = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=inst)
    session.execute = AsyncMock(return_value=res)
    session.commit = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.set_rag_config_status(
        rag_config_id=uuid4(), status=VersionStatus.PUBLISHED
    )
    rag_repo.cache_adapter.delete.assert_awaited()


@pytest.mark.asyncio
async def test_get_document_by_hash(rag_repo: RagRepository) -> None:
    session = async_session_double()
    doc = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=doc)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    assert await rag_repo.get_document_by_hash(tenant_id=uuid4(), content_hash="h") is doc


@pytest.mark.asyncio
async def test_create_document(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    out = await rag_repo.create_document(
        tenant_id=uuid4(),
        source="s",
        doc_type="t",
        content_hash="hash",
        content="c",
        version="1",
        metadata={},
    )
    assert out is session.add.call_args[0][0]


@pytest.mark.asyncio
async def test_update_document_embedding_status(rag_repo: RagRepository) -> None:
    session = async_session_double()
    res = MagicMock()
    res.rowcount = 1
    session.execute = AsyncMock(return_value=res)
    session.commit = AsyncMock()
    bind_rag_session(rag_repo, session)
    now = datetime.now(timezone.utc)
    ok = await rag_repo.update_document_embedding_status(
        document_id=uuid4(),
        status=EmbeddingStatus.COMPLETED,
        increment_attempts=True,
        started_at=now,
        completed_at=now,
    )
    assert ok is True


@pytest.mark.asyncio
async def test_list_documents_no_tracer(rag_repo_no_tracer: RagRepository) -> None:
    session = async_session_double()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert (
        await rag_repo_no_tracer.list_documents(tenant_id=uuid4(), limit=10) == []
    )


@pytest.mark.asyncio
async def test_count_documents_for_user(rag_repo: RagRepository) -> None:
    session = async_session_double()
    res = MagicMock()
    res.scalar = MagicMock(return_value=5)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    assert await rag_repo.count_documents_for_user(tenant_id=uuid4(), user_id="u") == 5


@pytest.mark.asyncio
async def test_count_user_memory_documents_for_rag_config(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    res = MagicMock()
    res.scalar = MagicMock(return_value=2)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    n = await rag_repo.count_user_memory_documents_for_rag_config(
        tenant_id=uuid4(), user_id="u", rag_config_id=uuid4()
    )
    assert n == 2


@pytest.mark.asyncio
async def test_count_documents_by_embedding_status(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    res = MagicMock()
    res.scalar = MagicMock(return_value=7)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    n = await rag_repo.count_documents_by_embedding_status(
        tenant_id=uuid4(), rag_config_id=uuid4(), statuses=["pending"]
    )
    assert n == 7


@pytest.mark.asyncio
async def test_list_chunks_no_tracer(rag_repo_no_tracer: RagRepository) -> None:
    session = async_session_double()
    ch = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [ch]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert await rag_repo_no_tracer.list_chunks(document_id=uuid4(), limit=50) == [ch]


@pytest.mark.asyncio
async def test_finalize_empty_chunks_raises(rag_repo: RagRepository) -> None:
    with pytest.raises(DomainValidationException):
        await rag_repo.finalize_document_embedding_with_usage(
            tenant_id=uuid4(),
            rag_config_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            document_id=uuid4(),
            chunks=[],
            completed_at=datetime.now(timezone.utc),
            quotas=None,
        )


@pytest.mark.asyncio
async def test_create_chunks_empty(rag_repo: RagRepository) -> None:
    await rag_repo.create_chunks(chunks=[])


@pytest.mark.asyncio
async def test_create_chunks_inserts(rag_repo: RagRepository) -> None:
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = uuid4()
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "c"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    session = async_session_double()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.create_chunks(chunks=[chunk])


@pytest.mark.asyncio
async def test_get_query_cache_no_tracer(rag_repo_no_tracer: RagRepository) -> None:
    session = async_session_double()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert (
        await rag_repo_no_tracer.get_query_cache(
            tenant_id=uuid4(),
            vector_store_id=uuid4(),
            vector_store_version=1,
            contract_hash="a",
            query_hash="b",
        )
        is None
    )


@pytest.mark.asyncio
async def test_update_query_cache_usage(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.update_query_cache_usage(cache_id=uuid4())


@pytest.mark.asyncio
async def test_search_similar_chunks_empty_embedding(
    rag_repo: RagRepository,
) -> None:
    assert (
        await rag_repo.search_similar_chunks(
            tenant_id=uuid4(),
            rag_config_id=uuid4(),
            vector_store_id=uuid4(),
            user_id=None,
            query_embedding=[],
            top_k=5,
            similarity_threshold=0.0,
            filters=None,
        )
        == []
    )


@pytest.mark.asyncio
async def test_search_similar_chunks_with_results(rag_repo: RagRepository) -> None:
    session = async_session_double()
    chunk = MagicMock()
    dist = 0.1
    created = datetime.now(timezone.utc)
    row_tuple = (chunk, dist, created, None)
    result = MagicMock()
    result.all = MagicMock(return_value=[row_tuple])
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo, session)
    out = await rag_repo.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id=None,
        query_embedding=[0.0, 0.0, 0.1],
        top_k=3,
        similarity_threshold=0.5,
        filters=None,
    )
    assert len(out) == 1
    assert out[0][0] is chunk


@pytest.mark.asyncio
async def test_search_similar_chunks_filters_source(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    chunk = MagicMock()
    result = MagicMock()
    result.all = MagicMock(return_value=[(chunk, 0.05, None, None)])
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo, session)
    await rag_repo.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id="uid",
        query_embedding=[0.1] * 3,
        top_k=2,
        similarity_threshold=0.0,
        filters={
            "source": "s",
            "doc_type": "d",
            "scope": "USER_MEMORY",
            "user_id": "u",
            "category": "c",
            "tool_intent": "t",
            "created_after": "2020-01-01T00:00:00+00:00",
            "expires_after": "2099-01-01",
        },
    )


@pytest.mark.asyncio
async def test_search_similar_chunks_scope_tenant_knowledge(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    chunk = MagicMock()
    result = MagicMock()
    result.all = MagicMock(return_value=[(chunk, 0.01, None, None)])
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo, session)
    await rag_repo.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id=None,
        query_embedding=[0.0, 1.0],
        top_k=1,
        similarity_threshold=0.0,
        filters={"scope": "TENANT_KNOWLEDGE"},
    )


@pytest.mark.asyncio
async def test_search_similar_chunks_no_tracer(
    rag_repo_no_tracer: RagRepository,
) -> None:
    session = async_session_double()
    chunk = MagicMock()
    result = MagicMock()
    result.all = MagicMock(return_value=[(chunk, 0.2, None, None)])
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo_no_tracer, session)
    out = await rag_repo_no_tracer.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id=None,
        query_embedding=[0.5, 0.5],
        top_k=1,
        similarity_threshold=0.0,
        filters=None,
    )
    assert len(out) == 1


@pytest.mark.asyncio
async def test_search_similar_chunks_below_threshold_filtered(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    chunk = MagicMock()
    result = MagicMock()
    result.all = MagicMock(return_value=[(chunk, 0.99, None, None)])
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo, session)
    out = await rag_repo.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id=None,
        query_embedding=[0.1, 0.2],
        top_k=5,
        similarity_threshold=0.95,
        filters=None,
    )
    assert out == []


@pytest.mark.asyncio
async def test_get_tenant_rag_summary(rag_repo: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock()
    row.vector_store_id = uuid4()
    row.name = "vs"
    row.rag_config_id = uuid4()
    row.status = "draft"
    cfg_rows = MagicMock()
    cfg_rows.all.return_value = [row]

    r1 = MagicMock()
    r1.scalar = MagicMock(return_value=1)
    r2 = MagicMock()
    r2.scalar = MagicMock(return_value=2)
    r3 = MagicMock()
    r3.scalar = MagicMock(return_value=3)
    r4 = MagicMock()
    r4.scalar = MagicMock(return_value=4)
    session.execute = AsyncMock(side_effect=[r1, r2, r3, r4, cfg_rows])
    bind_rag_session(rag_repo, session)
    summary = await rag_repo.get_tenant_rag_summary(tenant_id=uuid4(), configs_limit=10)
    assert summary.vector_stores_count == 1
    assert summary.documents_count == 2
    assert summary.chunks_count == 3
    assert summary.rag_configs_count == 4
    assert len(summary.configs) == 1


@pytest.mark.asyncio
async def test_get_document_by_id_no_tracer(
    rag_repo_no_tracer: RagRepository,
) -> None:
    session = async_session_double()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert await rag_repo_no_tracer.get_document_by_id(document_id=uuid4()) is None


@pytest.mark.asyncio
async def test_finalize_user_memory_missing_user_raises(
    rag_repo: RagRepository,
) -> None:
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = uuid4()
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = ""
    chunk.content_hash = "h"
    chunk.token_count = 0
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    session = async_session_double()
    doc = MagicMock()
    doc.rag_config_id = uuid4()
    doc.doc_metadata = {}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)
    session.execute = AsyncMock(return_value=doc_res)
    bind_rag_session(rag_repo, session)
    with pytest.raises(DomainValidationException):
        await rag_repo.finalize_document_embedding_with_usage(
            tenant_id=uuid4(),
            rag_config_id=doc.rag_config_id,
            corpus_kind="USER_MEMORY",
            document_id=uuid4(),
            chunks=[chunk],
            completed_at=datetime.now(timezone.utc),
            quotas=None,
        )


@pytest.mark.asyncio
async def test_finalize_document_not_found(rag_repo: RagRepository) -> None:
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = uuid4()
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    session = async_session_double()
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=doc_res)
    bind_rag_session(rag_repo, session)
    with pytest.raises(NotFoundServiceException):
        await rag_repo.finalize_document_embedding_with_usage(
            tenant_id=uuid4(),
            rag_config_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            document_id=uuid4(),
            chunks=[chunk],
            completed_at=datetime.now(timezone.utc),
            quotas=None,
        )


@pytest.mark.asyncio
async def test_finalize_rag_config_mismatch(rag_repo: RagRepository) -> None:
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = uuid4()
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    session = async_session_double()
    doc = MagicMock()
    doc.rag_config_id = uuid4()
    doc.doc_metadata = {}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)
    session.execute = AsyncMock(return_value=doc_res)
    bind_rag_session(rag_repo, session)
    with pytest.raises(NotFoundServiceException):
        await rag_repo.finalize_document_embedding_with_usage(
            tenant_id=uuid4(),
            rag_config_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            document_id=uuid4(),
            chunks=[chunk],
            completed_at=datetime.now(timezone.utc),
            quotas=None,
        )


@pytest.mark.asyncio
async def test_get_vector_store_no_tracer(rag_repo_no_tracer: RagRepository) -> None:
    session = async_session_double()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert await rag_repo_no_tracer.get_vector_store(uuid4()) is row


@pytest.mark.asyncio
async def test_get_document_by_hash_no_tracer(
    rag_repo_no_tracer: RagRepository,
) -> None:
    session = async_session_double()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo_no_tracer, session)
    assert (
        await rag_repo_no_tracer.get_document_by_hash(
            tenant_id=uuid4(), content_hash="h"
        )
        is row
    )


@pytest.mark.asyncio
async def test_list_documents_tracer_with_rag_config_filter(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    doc = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [doc]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    rcid = uuid4()
    out = await rag_repo.list_documents(
        tenant_id=uuid4(), limit=10, rag_config_id=rcid
    )
    assert out == [doc]


@pytest.mark.asyncio
async def test_list_chunks_tracer(rag_repo: RagRepository) -> None:
    session = async_session_double()
    ch = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [ch]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    assert await rag_repo.list_chunks(document_id=uuid4(), limit=20) == [ch]


@pytest.mark.asyncio
async def test_create_rag_config_from_source_version(
    rag_repo: RagRepository,
) -> None:
    tid = uuid4()
    source_id = uuid4()
    vid = uuid4()
    chunk_id = uuid4()
    source = MagicMock()
    source.tenant_id = tid
    source.version_major = 1
    source.version_minor = 0
    source.version_patch = 2
    source.config_hash = "h"
    source.options = {"k": "v"}
    source.chunking_rule_id = chunk_id
    source.corpus_kind = "TENANT_KNOWLEDGE"

    src_res = MagicMock()
    src_res.scalar_one_or_none = MagicMock(return_value=source)
    cr_row = MagicMock()
    cr_res = MagicMock()
    cr_res.scalar_one_or_none = MagicMock(return_value=cr_row)
    session = async_session_double()
    session.execute = AsyncMock(side_effect=[src_res, cr_res])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.create_rag_config(
        tenant_id=tid,
        source_version_id=source_id,
        vector_store_id=vid,
        created_by="u",
    )
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_rag_config_source_version_wrong_tenant(
    rag_repo: RagRepository,
) -> None:
    tid = uuid4()
    other = uuid4()
    source = MagicMock()
    source.tenant_id = other
    src_res = MagicMock()
    src_res.scalar_one_or_none = MagicMock(return_value=source)
    session = async_session_double()
    session.execute = AsyncMock(return_value=src_res)
    bind_rag_session(rag_repo, session)
    with pytest.raises(NotFoundServiceException):
        await rag_repo.create_rag_config(
            tenant_id=tid,
            source_version_id=uuid4(),
            vector_store_id=uuid4(),
            created_by="u",
        )


@pytest.mark.asyncio
async def test_finalize_lock_counter_integrity_error_then_fetch_row(
    rag_repo: RagRepository,
) -> None:
    tenant_id = uuid4()
    rag_cfg_id = uuid4()
    doc_id = uuid4()
    doc = MagicMock()
    doc.rag_config_id = rag_cfg_id
    doc.doc_metadata = {}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)

    lock_none = MagicMock()
    lock_none.scalar_one_or_none = MagicMock(return_value=None)
    tenant_row = MagicMock()
    tenant_row.document_count = 0
    tenant_row.chunk_count = 0
    lock_row = MagicMock()
    lock_row.scalar_one_or_none = MagicMock(return_value=tenant_row)

    session = async_session_double()
    session.begin_nested = MagicMock(return_value=nested_transaction_context())
    session.add = MagicMock()
    session.flush = AsyncMock(side_effect=IntegrityError("dup", None, None))
    session.execute = AsyncMock(
        side_effect=[
            doc_res,
            lock_none,
            lock_row,
            MagicMock(),
            MagicMock(),
        ]
    )
    bind_rag_session(rag_repo, session)
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = doc_id
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    await rag_repo.finalize_document_embedding_with_usage(
        tenant_id=tenant_id,
        rag_config_id=rag_cfg_id,
        corpus_kind="TENANT_KNOWLEDGE",
        document_id=doc_id,
        chunks=[chunk],
        completed_at=datetime.now(timezone.utc),
        quotas=None,
    )


@pytest.mark.asyncio
async def test_finalize_lock_counter_still_missing_after_integrity_error_raises(
    rag_repo: RagRepository,
) -> None:
    tenant_id = uuid4()
    rag_cfg_id = uuid4()
    doc_id = uuid4()
    doc = MagicMock()
    doc.rag_config_id = rag_cfg_id
    doc.doc_metadata = {}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)

    lock_none = MagicMock()
    lock_none.scalar_one_or_none = MagicMock(return_value=None)
    lock_still_missing = MagicMock()
    lock_still_missing.scalar_one_or_none = MagicMock(return_value=None)

    session = async_session_double()
    session.begin_nested = MagicMock(return_value=nested_transaction_context())
    session.add = MagicMock()
    session.flush = AsyncMock(side_effect=IntegrityError("dup", None, None))
    session.execute = AsyncMock(
        side_effect=[doc_res, lock_none, lock_still_missing]
    )
    bind_rag_session(rag_repo, session)
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = doc_id
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    with pytest.raises(NotFoundServiceException):
        await rag_repo.finalize_document_embedding_with_usage(
            tenant_id=tenant_id,
            rag_config_id=rag_cfg_id,
            corpus_kind="TENANT_KNOWLEDGE",
            document_id=doc_id,
            chunks=[chunk],
            completed_at=datetime.now(timezone.utc),
            quotas=None,
        )


@pytest.mark.asyncio
async def test_finalize_tenant_knowledge_success(rag_repo: RagRepository) -> None:
    tenant_id = uuid4()
    rag_cfg_id = uuid4()
    doc_id = uuid4()
    doc = MagicMock()
    doc.rag_config_id = rag_cfg_id
    doc.doc_metadata = {}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)
    tenant_row = MagicMock()
    tenant_row.document_count = 0
    tenant_row.chunk_count = 0
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=tenant_row)
    session = async_session_double()
    session.execute = AsyncMock(
        side_effect=[doc_res, lock_res, MagicMock(), MagicMock()]
    )
    bind_rag_session(rag_repo, session)
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = doc_id
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    await rag_repo.finalize_document_embedding_with_usage(
        tenant_id=tenant_id,
        rag_config_id=rag_cfg_id,
        corpus_kind="TENANT_KNOWLEDGE",
        document_id=doc_id,
        chunks=[chunk],
        completed_at=datetime.now(timezone.utc),
        quotas=None,
    )
    assert int(tenant_row.document_count) >= 1
    assert int(tenant_row.chunk_count) >= 1


@pytest.mark.asyncio
async def test_finalize_quota_max_documents_per_tenant_exceeded(
    rag_repo: RagRepository,
) -> None:
    tenant_id = uuid4()
    rag_cfg_id = uuid4()
    doc_id = uuid4()
    doc = MagicMock()
    doc.rag_config_id = rag_cfg_id
    doc.doc_metadata = {}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)
    tenant_row = MagicMock()
    tenant_row.document_count = 10
    tenant_row.chunk_count = 0
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=tenant_row)
    session = async_session_double()
    session.execute = AsyncMock(side_effect=[doc_res, lock_res])
    bind_rag_session(rag_repo, session)
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = doc_id
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    with pytest.raises(DomainValidationException):
        await rag_repo.finalize_document_embedding_with_usage(
            tenant_id=tenant_id,
            rag_config_id=rag_cfg_id,
            corpus_kind="TENANT_KNOWLEDGE",
            document_id=doc_id,
            chunks=[chunk],
            completed_at=datetime.now(timezone.utc),
            quotas=RagIngestQuotas(max_documents_per_tenant=10),
        )


@pytest.mark.asyncio
async def test_finalize_user_memory_success_with_tenant_quota_checks(
    rag_repo: RagRepository,
) -> None:
    tenant_id = uuid4()
    rag_cfg_id = uuid4()
    doc_id = uuid4()
    doc = MagicMock()
    doc.rag_config_id = rag_cfg_id
    doc.doc_metadata = {"user_id": "alice"}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)
    user_row = MagicMock()
    user_row.document_count = 0
    user_row.chunk_count = 0
    tenant_row = MagicMock()
    tenant_row.document_count = 0
    tenant_row.chunk_count = 0
    ul = MagicMock()
    ul.scalar_one_or_none = MagicMock(return_value=user_row)
    tl = MagicMock()
    tl.scalar_one_or_none = MagicMock(return_value=tenant_row)
    session = async_session_double()
    session.execute = AsyncMock(
        side_effect=[doc_res, ul, tl, MagicMock(), MagicMock()]
    )
    bind_rag_session(rag_repo, session)
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = doc_id
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    await rag_repo.finalize_document_embedding_with_usage(
        tenant_id=tenant_id,
        rag_config_id=rag_cfg_id,
        corpus_kind="USER_MEMORY",
        document_id=doc_id,
        chunks=[chunk],
        completed_at=datetime.now(timezone.utc),
        quotas=RagIngestQuotas(
            max_documents_per_tenant=100,
            max_chunks_per_tenant=100,
            max_documents_per_user=100,
            max_chunks_per_user=100,
        ),
    )


@pytest.mark.asyncio
async def test_finalize_user_memory_user_id_non_string_coerced(
    rag_repo: RagRepository,
) -> None:
    tenant_id = uuid4()
    rag_cfg_id = uuid4()
    doc_id = uuid4()
    doc = MagicMock()
    doc.rag_config_id = rag_cfg_id
    doc.doc_metadata = {"user_id": 42}
    doc_res = MagicMock()
    doc_res.scalar_one_or_none = MagicMock(return_value=doc)
    user_row = MagicMock()
    user_row.document_count = 0
    user_row.chunk_count = 0
    ul = MagicMock()
    ul.scalar_one_or_none = MagicMock(return_value=user_row)
    session = async_session_double()
    session.execute = AsyncMock(
        side_effect=[doc_res, ul, MagicMock(), MagicMock()]
    )
    bind_rag_session(rag_repo, session)
    chunk = MagicMock()
    chunk.chunk_id = uuid4()
    chunk.document_id = doc_id
    chunk.vector_store_id = uuid4()
    chunk.chunk_index = 0
    chunk.content = "x"
    chunk.content_hash = "h"
    chunk.token_count = 1
    chunk.embedding = [0.1]
    chunk.chunk_metadata = {}
    await rag_repo.finalize_document_embedding_with_usage(
        tenant_id=tenant_id,
        rag_config_id=rag_cfg_id,
        corpus_kind="USER_MEMORY",
        document_id=doc_id,
        chunks=[chunk],
        completed_at=datetime.now(timezone.utc),
        quotas=None,
    )


@pytest.mark.asyncio
async def test_search_similar_chunks_no_tracer_skips_below_threshold(
    rag_repo_no_tracer: RagRepository,
) -> None:
    session = async_session_double()
    chunk = MagicMock()
    result = MagicMock()
    result.all = MagicMock(
        return_value=[
            (chunk, 0.99, None, None),
        ]
    )
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo_no_tracer, session)
    out = await rag_repo_no_tracer.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id=None,
        query_embedding=[0.1, 0.2],
        top_k=5,
        similarity_threshold=0.5,
        filters=None,
    )
    assert out == []


@pytest.mark.asyncio
async def test_search_similar_chunks_non_tracer_full_loop(
    rag_repo_no_tracer: RagRepository,
) -> None:
    session = async_session_double()
    chunk = MagicMock()
    result = MagicMock()
    result.all = MagicMock(
        return_value=[(chunk, 0.1, datetime.now(timezone.utc), "obs")]
    )
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo_no_tracer, session)
    out = await rag_repo_no_tracer.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id=None,
        query_embedding=[0.0, 0.5],
        top_k=5,
        similarity_threshold=0.0,
        filters=None,
    )
    assert len(out) == 1
    assert out[0][3] == "obs"


@pytest.mark.asyncio
async def test_search_similar_chunks_created_after_non_string_skipped(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    chunk = MagicMock()
    result = MagicMock()
    result.all = MagicMock(return_value=[(chunk, 0.05, None, None)])
    session.execute = AsyncMock(return_value=result)
    bind_rag_session(rag_repo, session)
    await rag_repo.search_similar_chunks(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        vector_store_id=uuid4(),
        user_id=None,
        query_embedding=[0.1, 0.2],
        top_k=2,
        similarity_threshold=0.0,
        filters={"created_after": datetime(2020, 1, 1, tzinfo=timezone.utc)},
    )


@pytest.mark.asyncio
async def test_get_published_rag_config_id_for_vector_store(
    rag_repo: RagRepository,
) -> None:
    session = async_session_double()
    rid = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=rid)
    session.execute = AsyncMock(return_value=res)
    bind_rag_session(rag_repo, session)
    out = await rag_repo.get_published_rag_config_id_for_vector_store(
        tenant_id=uuid4(), vector_store_id=uuid4()
    )
    assert out == rid


@pytest.mark.asyncio
async def test_save_query_cache(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    bind_rag_session(rag_repo, session)
    entry = MagicMock()
    out = await rag_repo.save_query_cache(cache_entry=entry)
    session.add.assert_called_once_with(entry)
    assert out is entry


@pytest.mark.asyncio
async def test_invalidate_query_cache_vector_store(rag_repo: RagRepository) -> None:
    session = async_session_double()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    bind_rag_session(rag_repo, session)
    await rag_repo.invalidate_query_cache_vector_store(
        tenant_id=uuid4(), vector_store_id=uuid4()
    )
