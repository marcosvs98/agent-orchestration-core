from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import (
    DEFAULT_EMBEDDING_DIMENSION,
    RagConfigOptions,
    RagDocumentCreate,
)
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

    @pytest.mark.asyncio
    async def test_get_context_query_cache_embedding_as_numpy_no_bool_eval(
        self,
        rag_runtime_service: RagRuntimeService,
        repository: MagicMock,
        embedding_adapter: MagicMock,
    ) -> None:
        np = pytest.importorskip("numpy")
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
        repository.get_query_cache.return_value = SimpleNamespace(
            query_cache_id=uuid4(),
            embedding_model="text-embedding-3-small",
            embedding_dimension=DEFAULT_EMBEDDING_DIMENSION,
            embedding=np.ones(DEFAULT_EMBEDDING_DIMENSION, dtype=np.float64),
            embedding_512=None,
        )
        repository.update_query_cache_usage = AsyncMock()

        await rag_runtime_service.get_context(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            user_input="same query hash path",
        )

        embedding_adapter.generate_embedding.assert_not_called()
        call_kw = repository.search_similar_chunks.await_args.kwargs
        assert len(call_kw["query_embedding"]) == DEFAULT_EMBEDDING_DIMENSION
        assert call_kw["query_embedding"][0] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_ingest_documents_batch_counts_failures_and_continues(
        self,
        rag_runtime_service: RagRuntimeService,
    ) -> None:
        """Verify batch ingest continues after per-document failures."""
        tenant_id = uuid4()
        rag_config_id = uuid4()

        documents = [
            RagDocumentCreate(
                source="assistente-bolso",
                doc_type="identity_proposito",
                content="hello-1",
                version="1",
                metadata={"topic": "identity_proposito"},
            ),
            RagDocumentCreate(
                source="assistente-bolso",
                doc_type="escopo",
                content="hello-2",
                version="1",
                metadata={"topic": "scope"},
            ),
            RagDocumentCreate(
                source="assistente-bolso",
                doc_type="faq_conexao_bancaria",
                content="hello-3",
                version="1",
                metadata={"topic": "faq"},
            ),
        ]

        rag_runtime_service.ingest_document = AsyncMock(
            side_effect=[MagicMock(), Exception("boom"), MagicMock()]
        )

        succeeded_count, failed_count = (
            await rag_runtime_service.ingest_documents_batch(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                documents=documents,
            )
        )

        assert succeeded_count == 2
        assert failed_count == 1
        assert rag_runtime_service.ingest_document.await_count == 3
