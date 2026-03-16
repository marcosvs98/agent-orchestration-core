from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import DEFAULT_EMBEDDING_DIMENSION, RagConfigOptions
from domain.rag.services.rag_runtime_service import RagRuntimeService


class TestRagRuntimeServiceEmbeddingDimension:
    @pytest.fixture
    def repository(self) -> MagicMock:
        repo = MagicMock(spec=RagRepository)
        repo.get_rag_config = AsyncMock()
        repo.get_query_cache = AsyncMock(return_value=None)
        repo.save_query_cache = AsyncMock()
        repo.search_similar_chunks = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def embedding_adapter(self) -> MagicMock:
        adapter = MagicMock()
        adapter.generate_embedding = AsyncMock(
            return_value=[0.1] * DEFAULT_EMBEDDING_DIMENSION
        )
        return adapter

    @pytest.fixture
    def tracer(self) -> MagicMock:
        tracer = MagicMock()
        tracer.observe = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        return tracer

    @pytest.fixture
    def rag_runtime_service(
        self,
        repository: MagicMock,
        embedding_adapter: MagicMock,
        tracer: MagicMock,
    ) -> RagRuntimeService:
        return RagRuntimeService(
            repository=repository,
            embedding_adapter=embedding_adapter,
            tracer=tracer,
        )

    @pytest.mark.asyncio
    async def test_get_context_accepts_supported_embedding_dimension(
        self,
        rag_runtime_service: RagRuntimeService,
        repository: MagicMock,
    ) -> None:
        tenant_id = uuid4()
        rag_config_id = uuid4()
        config_options = {
            "embedding": {
                "provider": "OPENAI",
                "model_alias": "text-embedding-3-small",
                "dimension": DEFAULT_EMBEDDING_DIMENSION,
            },
            "chunking": {"target_tokens": 500, "overlap_tokens": 50},
            "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
            "generation_contract": {"allow_extrapolation": False},
        }
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            options=config_options,
        )

        result = await rag_runtime_service.get_context(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            user_input="query",
        )

        assert result.eligible is False
        assert result.reason.value == "NO_MATCHES"
