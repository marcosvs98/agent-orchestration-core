"""Smoke coverage for RagRuntimeService with current constructor (embedding executor path)."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import DEFAULT_EMBEDDING_DIMENSION, RagConfigOptions
from domain.rag.services.embedding_executor import EmbeddingExecutor
from domain.rag.services.rag_runtime_service import RagRuntimeService


def _tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


def _rag_policy() -> MagicMock:
    svc = MagicMock(spec=RagPolicyService)
    resolved = SimpleNamespace(definition=SimpleNamespace(ingest_quotas=None))
    svc.resolve = AsyncMock(return_value=resolved)
    return svc


def _ai_repo() -> MagicMock:
    ai = MagicMock(spec=AIRepository)
    ai.get_model_by_name = AsyncMock(
        return_value=SimpleNamespace(
            name="text-embedding-3-small",
            is_active=True,
            type="EMBEDDING",
            provider="openai",
        )
    )
    return ai


def _embedding_executor() -> MagicMock:
    emb = MagicMock(spec=EmbeddingExecutor)
    emb.execute = AsyncMock(return_value=[0.1] * DEFAULT_EMBEDDING_DIMENSION)
    emb.execute_batch = AsyncMock(
        return_value=[[0.1] * DEFAULT_EMBEDDING_DIMENSION, [0.2] * DEFAULT_EMBEDDING_DIMENSION]
    )
    return emb


@pytest.fixture
def rag_repo() -> MagicMock:
    repo = MagicMock(spec=RagRepository)
    repo.get_rag_config = AsyncMock()
    repo.get_vector_store = AsyncMock(
        return_value=SimpleNamespace(
            embedding_model="text-embedding-3-small",
            embedding_dimension=DEFAULT_EMBEDDING_DIMENSION,
            metric="cosine",
            version=1,
        )
    )
    repo.get_query_cache = AsyncMock(return_value=None)
    repo.save_query_cache = AsyncMock()
    repo.invalidate_query_cache_contract = AsyncMock()
    repo.search_similar_chunks = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def rag_service(
    rag_repo: MagicMock,
) -> RagRuntimeService:
    return RagRuntimeService(
        repository=rag_repo,
        tracer=_tracer(),
        rag_policy_service=_rag_policy(),
        ai_repository=_ai_repo(),
        embedding_executor=_embedding_executor(),
    )


@pytest.mark.asyncio
async def test_get_context_returns_no_matches_when_search_empty(
    rag_service: RagRuntimeService,
    rag_repo: MagicMock,
) -> None:
    tenant_id = uuid4()
    rag_config_id = uuid4()
    vector_store_id = uuid4()
    opts = RagConfigOptions.model_validate(
        {
            "embedding": {
                "provider": "OPENAI",
                "model_alias": "text-embedding-3-small",
                "dimension": DEFAULT_EMBEDDING_DIMENSION,
            },
            "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
            "generation_contract": {"allow_extrapolation": False},
        }
    )
    rag_repo.get_rag_config.return_value = SimpleNamespace(
        tenant_id=tenant_id,
        chunking_rule_id=uuid4(),
        corpus_kind="TENANT_KNOWLEDGE",
        options=opts.model_dump(mode="json"),
        vector_store_id=vector_store_id,
    )

    result = await rag_service.get_context(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        user_input="hello world",
    )

    assert result.eligible is False
    assert result.reason.value == "NO_MATCHES"
