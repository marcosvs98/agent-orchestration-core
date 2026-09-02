from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.services.embedding_executor import EmbeddingExecutor
from domain.rag.schemas.rag import (
    DEFAULT_EMBEDDING_DIMENSION,
    RagDocumentCreate,
)
from domain.rag.services.rag_runtime_service import RagRuntimeService
from exceptions.service_exceptions import DomainValidationException, NotFoundServiceException


class TestRagRuntimeServiceEmbeddingDimension:
    @pytest.fixture
    def repository(self) -> MagicMock:
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
    def ai_repository(self) -> MagicMock:
        ai = MagicMock(spec=AIRepository)
        ai.get_model_by_name = AsyncMock(
            return_value=SimpleNamespace(
                name="text-embedding-3-small",
                is_active=True,
                type="EMBEDDING",
                provider="openai",
            )
        )
        ai.get_model = AsyncMock(return_value=None)
        return ai

    @pytest.fixture
    def embedding_executor(self) -> MagicMock:
        ex = MagicMock(spec=EmbeddingExecutor)
        ex.execute = AsyncMock(return_value=[0.1] * DEFAULT_EMBEDDING_DIMENSION)
        ex.execute_batch = AsyncMock(return_value=[[0.1] * DEFAULT_EMBEDDING_DIMENSION])
        return ex

    @pytest.fixture
    def tracer(self) -> MagicMock:
        tracer = MagicMock()
        tracer.observe = MagicMock(
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        )
        return tracer

    @pytest.fixture
    def rag_policy_service(self) -> MagicMock:
        svc = MagicMock()
        resolved = SimpleNamespace(
            definition=SimpleNamespace(ingest_quotas=None),
        )
        svc.resolve = AsyncMock(return_value=resolved)
        return svc

    @pytest.fixture
    def rag_runtime_service(
        self,
        repository: MagicMock,
        ai_repository: MagicMock,
        embedding_executor: MagicMock,
        tracer: MagicMock,
        rag_policy_service: MagicMock,
    ) -> RagRuntimeService:
        return RagRuntimeService(
            repository=repository,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
            ai_repository=ai_repository,
            embedding_executor=embedding_executor,
        )

    @pytest.mark.asyncio
    async def test_get_context_accepts_supported_embedding_dimension(
        self,
        rag_runtime_service: RagRuntimeService,
        repository: MagicMock,
    ) -> None:
        tenant_id = uuid4()
        rag_config_id = uuid4()
        vector_store_id = uuid4()
        config_options = {
            "embedding": {
                "provider": "OPENAI",
                "model_alias": "text-embedding-3-small",
                "dimension": DEFAULT_EMBEDDING_DIMENSION,
            },
            "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
            "generation_contract": {"allow_extrapolation": False},
        }
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            chunking_rule_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            options=config_options,
            vector_store_id=vector_store_id,
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
        embedding_executor: MagicMock,
    ) -> None:
        np = pytest.importorskip("numpy")
        tenant_id = uuid4()
        rag_config_id = uuid4()
        vector_store_id = uuid4()
        config_options = {
            "embedding": {
                "provider": "OPENAI",
                "model_alias": "text-embedding-3-small",
                "dimension": DEFAULT_EMBEDDING_DIMENSION,
            },
            "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
            "generation_contract": {"allow_extrapolation": False},
        }
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            chunking_rule_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            options=config_options,
            vector_store_id=vector_store_id,
        )
        repository.get_query_cache.return_value = SimpleNamespace(
            query_cache_id=uuid4(),
            embedding=np.ones(DEFAULT_EMBEDDING_DIMENSION, dtype=np.float64),
        )
        repository.update_query_cache_usage = AsyncMock()

        await rag_runtime_service.get_context(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            user_input="same query hash path",
        )

        embedding_executor.execute.assert_not_called()
        repository.get_query_cache.assert_awaited_once()
        qc_kw = repository.get_query_cache.await_args.kwargs
        assert qc_kw["tenant_id"] == tenant_id
        assert qc_kw["vector_store_id"] == vector_store_id
        call_kw = repository.search_similar_chunks.await_args.kwargs
        assert len(call_kw["query_embedding"]) == DEFAULT_EMBEDDING_DIMENSION
        assert call_kw["query_embedding"][0] == pytest.approx(1.0)
        assert call_kw["rag_config_id"] == rag_config_id
        assert call_kw["vector_store_id"] == vector_store_id

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

        succeeded_count, failed_count = await rag_runtime_service.ingest_documents_batch(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            documents=documents,
        )

        assert succeeded_count == 2
        assert failed_count == 1
        assert rag_runtime_service.ingest_document.await_count == 3


class TestRagRuntimeServiceEmbeddingModelCatalog:
    @pytest.fixture
    def repository(self) -> MagicMock:
        repo = MagicMock(spec=RagRepository)
        repo.get_rag_config = AsyncMock()
        repo.get_vector_store = AsyncMock(
            return_value=SimpleNamespace(
                embedding_model="text-embedding-3-large",
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
    def embedding_executor(self) -> MagicMock:
        ex = MagicMock(spec=EmbeddingExecutor)
        ex.execute = AsyncMock(return_value=[0.1] * DEFAULT_EMBEDDING_DIMENSION)
        ex.execute_batch = AsyncMock(return_value=[[0.1] * DEFAULT_EMBEDDING_DIMENSION])
        return ex

    @pytest.fixture
    def tracer(self) -> MagicMock:
        tracer = MagicMock()
        tracer.observe = MagicMock(
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        )
        return tracer

    @pytest.fixture
    def rag_policy_service(self) -> MagicMock:
        svc = MagicMock()
        resolved = SimpleNamespace(
            definition=SimpleNamespace(ingest_quotas=None),
        )
        svc.resolve = AsyncMock(return_value=resolved)
        return svc

    @pytest.mark.asyncio
    async def test_get_context_resolves_embedding_model_id_via_catalog(
        self,
        repository: MagicMock,
        embedding_executor: MagicMock,
        tracer: MagicMock,
        rag_policy_service: MagicMock,
    ) -> None:
        model_id = uuid4()
        ai_repo = MagicMock()
        ai_repo.get_model = AsyncMock(
            return_value=SimpleNamespace(
                name="text-embedding-3-large",
                is_active=True,
                type="EMBEDDING",
                provider="openai",
            )
        )
        svc = RagRuntimeService(
            repository=repository,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
            ai_repository=ai_repo,
            embedding_executor=embedding_executor,
        )
        tenant_id = uuid4()
        rag_config_id = uuid4()
        vector_store_id = uuid4()
        config_options = {
            "embedding": {
                "provider": "OPENAI",
                "model_alias": "text-embedding-3-small",
                "dimension": DEFAULT_EMBEDDING_DIMENSION,
                "model_id": str(model_id),
            },
            "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
            "generation_contract": {"allow_extrapolation": False},
        }
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            chunking_rule_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            options=config_options,
            vector_store_id=vector_store_id,
        )

        await svc.get_context(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            user_input="q",
        )

        ai_repo.get_model.assert_awaited_once_with(model_id)
        embedding_executor.execute.assert_awaited_once()
        req = embedding_executor.execute.await_args[0][0]
        assert req.contract.model == "text-embedding-3-large"
        save_kw = repository.save_query_cache.await_args.kwargs["cache_entry"]
        assert save_kw.vector_store_id == vector_store_id
        assert save_kw.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_get_context_model_id_missing_row_raises(
        self,
        repository: MagicMock,
        embedding_executor: MagicMock,
        tracer: MagicMock,
        rag_policy_service: MagicMock,
    ) -> None:
        model_id = uuid4()
        ai_repo = MagicMock()
        ai_repo.get_model = AsyncMock(return_value=None)
        svc = RagRuntimeService(
            repository=repository,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
            ai_repository=ai_repo,
            embedding_executor=embedding_executor,
        )
        tenant_id = uuid4()
        rag_config_id = uuid4()
        vector_store_id = uuid4()
        config_options = {
            "embedding": {
                "provider": "OPENAI",
                "model_alias": "text-embedding-3-small",
                "dimension": DEFAULT_EMBEDDING_DIMENSION,
                "model_id": str(model_id),
            },
            "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
            "generation_contract": {"allow_extrapolation": False},
        }
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            chunking_rule_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            options=config_options,
            vector_store_id=vector_store_id,
        )

        with pytest.raises(NotFoundServiceException):
            await svc.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_input="q",
            )

    @pytest.mark.asyncio
    async def test_get_context_model_id_inactive_raises(
        self,
        repository: MagicMock,
        embedding_executor: MagicMock,
        tracer: MagicMock,
        rag_policy_service: MagicMock,
    ) -> None:
        model_id = uuid4()
        ai_repo = MagicMock()
        ai_repo.get_model = AsyncMock(
            return_value=SimpleNamespace(
                name="text-embedding-3-large",
                is_active=False,
                type="EMBEDDING",
                provider="openai",
            )
        )
        svc = RagRuntimeService(
            repository=repository,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
            ai_repository=ai_repo,
            embedding_executor=embedding_executor,
        )
        tenant_id = uuid4()
        rag_config_id = uuid4()
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            chunking_rule_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            options={
                "embedding": {
                    "provider": "OPENAI",
                    "model_alias": "text-embedding-3-small",
                    "dimension": DEFAULT_EMBEDDING_DIMENSION,
                    "model_id": str(model_id),
                },
                "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
                "generation_contract": {"allow_extrapolation": False},
            },
            vector_store_id=uuid4(),
        )
        with pytest.raises(DomainValidationException):
            await svc.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_input="q",
            )

    @pytest.mark.asyncio
    async def test_get_context_model_id_provider_missing_raises(
        self,
        repository: MagicMock,
        embedding_executor: MagicMock,
        tracer: MagicMock,
        rag_policy_service: MagicMock,
    ) -> None:
        model_id = uuid4()
        ai_repo = MagicMock()
        ai_repo.get_model = AsyncMock(
            return_value=SimpleNamespace(
                name="text-embedding-3-large",
                is_active=True,
                type="EMBEDDING",
                provider="",
            )
        )
        svc = RagRuntimeService(
            repository=repository,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
            ai_repository=ai_repo,
            embedding_executor=embedding_executor,
        )
        tenant_id = uuid4()
        rag_config_id = uuid4()
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            chunking_rule_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            options={
                "embedding": {
                    "provider": "OPENAI",
                    "model_alias": "text-embedding-3-small",
                    "dimension": DEFAULT_EMBEDDING_DIMENSION,
                    "model_id": str(model_id),
                },
                "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
                "generation_contract": {"allow_extrapolation": False},
            },
            vector_store_id=uuid4(),
        )
        with pytest.raises(DomainValidationException):
            await svc.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_input="q",
            )

    @pytest.mark.asyncio
    async def test_get_context_retrieval_dimension_vector_store_mismatch_raises(
        self,
        repository: MagicMock,
        embedding_executor: MagicMock,
        tracer: MagicMock,
        rag_policy_service: MagicMock,
    ) -> None:
        repository.get_vector_store = AsyncMock(
            return_value=SimpleNamespace(
                embedding_model="text-embedding-3-large",
                embedding_dimension=1536,
                metric="cosine",
                version=1,
            )
        )
        ai_repo = MagicMock()
        model_id = uuid4()
        ai_repo.get_model = AsyncMock(
            return_value=SimpleNamespace(
                name="text-embedding-3-small",
                is_active=True,
                type="EMBEDDING",
                provider="openai",
            )
        )
        svc = RagRuntimeService(
            repository=repository,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
            ai_repository=ai_repo,
            embedding_executor=embedding_executor,
        )
        tenant_id = uuid4()
        rag_config_id = uuid4()
        repository.get_rag_config.return_value = SimpleNamespace(
            tenant_id=tenant_id,
            chunking_rule_id=uuid4(),
            corpus_kind="TENANT_KNOWLEDGE",
            options={
                "embedding": {
                    "provider": "OPENAI",
                    "model_alias": "text-embedding-3-small",
                    "dimension": 3072,
                    "model_id": str(model_id),
                },
                "retrieval": {"top_k": 5, "similarity_threshold": 0.5},
                "generation_contract": {"allow_extrapolation": False},
            },
            vector_store_id=uuid4(),
        )
        with pytest.raises(DomainValidationException) as excinfo:
            await svc.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_input="q",
            )
        assert excinfo.value.message == "rag_retrieval_embedding_dimension_vector_store_mismatch"


class TestRagRuntimeServiceUserMemoryVectorDocumentCap:
    @pytest.fixture
    def repository(self) -> MagicMock:
        return MagicMock(spec=RagRepository)

    @pytest.fixture
    def ai_repository(self) -> MagicMock:
        return MagicMock(spec=AIRepository)

    @pytest.fixture
    def embedding_executor(self) -> MagicMock:
        ex = MagicMock(spec=EmbeddingExecutor)
        ex.execute = AsyncMock()
        ex.execute_batch = AsyncMock()
        return ex

    @pytest.fixture
    def tracer(self) -> MagicMock:
        tracer = MagicMock()
        tracer.observe = MagicMock(
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        )
        return tracer

    @pytest.fixture
    def rag_policy_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def rag_runtime_service(
        self,
        repository: MagicMock,
        ai_repository: MagicMock,
        embedding_executor: MagicMock,
        tracer: MagicMock,
        rag_policy_service: MagicMock,
    ) -> RagRuntimeService:
        return RagRuntimeService(
            repository=repository,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
            ai_repository=ai_repository,
            embedding_executor=embedding_executor,
        )

    @pytest.mark.asyncio
    async def test_resolve_cap_uses_app_when_no_ingest_quota(
        self,
        rag_runtime_service: RagRuntimeService,
        rag_policy_service: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import domain.rag.services.rag_runtime_service as cap_mod

        monkeypatch.setattr(cap_mod.settings, "MAX_USER_MEMORY_DOCUMENTS", 800)
        rag_policy_service.resolve = AsyncMock(
            return_value=SimpleNamespace(
                definition=SimpleNamespace(ingest_quotas=None),
            )
        )
        out = await rag_runtime_service.resolve_user_memory_vector_document_cap(
            tenant_id=uuid4(),
        )
        assert out["effective_cap"] == 800
        assert out["app_max_user_memory_documents"] == 800
        assert out["tenant_max_documents_per_user"] is None
        assert out["binding"] == "app"
        assert out["reason_code"] == "app_max_user_memory_documents"

    @pytest.mark.asyncio
    async def test_resolve_cap_uses_min_when_tenant_quota_stricter(
        self,
        rag_runtime_service: RagRuntimeService,
        rag_policy_service: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import domain.rag.services.rag_runtime_service as cap_mod

        monkeypatch.setattr(cap_mod.settings, "MAX_USER_MEMORY_DOCUMENTS", 800)
        quotas = SimpleNamespace(max_documents_per_user=120)
        rag_policy_service.resolve = AsyncMock(
            return_value=SimpleNamespace(
                definition=SimpleNamespace(ingest_quotas=quotas),
            )
        )
        out = await rag_runtime_service.resolve_user_memory_vector_document_cap(
            tenant_id=uuid4(),
        )
        assert out["effective_cap"] == 120
        assert out["tenant_max_documents_per_user"] == 120
        assert out["binding"] == "rag_policy"
        assert out["reason_code"] == "rag_ingest_quota_user_documents"

    @pytest.mark.asyncio
    async def test_resolve_cap_uses_app_when_tenant_quota_looser(
        self,
        rag_runtime_service: RagRuntimeService,
        rag_policy_service: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import domain.rag.services.rag_runtime_service as cap_mod

        monkeypatch.setattr(cap_mod.settings, "MAX_USER_MEMORY_DOCUMENTS", 200)
        quotas = SimpleNamespace(max_documents_per_user=900)
        rag_policy_service.resolve = AsyncMock(
            return_value=SimpleNamespace(
                definition=SimpleNamespace(ingest_quotas=quotas),
            )
        )
        out = await rag_runtime_service.resolve_user_memory_vector_document_cap(
            tenant_id=uuid4(),
        )
        assert out["effective_cap"] == 200
        assert out["tenant_max_documents_per_user"] == 900
        assert out["binding"] == "app"
        assert out["reason_code"] == "app_max_user_memory_documents"
