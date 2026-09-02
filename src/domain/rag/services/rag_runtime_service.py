from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal, TypedDict
from uuid import UUID, uuid4

import tiktoken

import settings

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.governance.schemas.rag_policy import RagIngestQuotas, ResolvedRagPolicy
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.embedding import (
    EmbeddingContract,
    EmbeddingBatchExecutionRequest,
    EmbeddingExecutionRequest,
)
from domain.rag.services.embedding_executor import EmbeddingExecutor
from domain.rag.schemas.embedding_job import EmbeddingStatus
from domain.rag.schemas.rag import (
    RagChunkingStrategy,
    RagConfigOptions,
    RagEmbeddingOptions,
    RagContext,
    RagContextReason,
    RagContextItem,
    RagCorpusKind,
    RagDocument,
    RagDocumentCreate,
    RagChunk,
    RagPreparedDocument,
    RecursiveCharacterChunkingParams,
    SemanticChunkingParams,
    TokenWindowChunkingParams,
    PerPageChunkingParams,
    parse_rag_chunking_rule_params,
    SUPPORTED_EMBEDDING_DIMENSIONS,
)
from adapters.observability.logging import get_logger
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database.models.rag.rag_chunk import RagChunk as RagChunkModel
from infra.database.models.rag.rag_query_cache import (
    RagQueryCache as RagQueryCacheModel,
)
from infra.database.models.rag.vector_store import VectorStore as VectorStoreModel
import numpy as np

logger = get_logger(__name__)


class UserMemoryVectorDocumentCap(TypedDict):
    effective_cap: int
    app_max_user_memory_documents: int
    tenant_max_documents_per_user: int | None
    binding: Literal["app", "rag_policy"]
    reason_code: Literal["app_max_user_memory_documents", "rag_ingest_quota_user_documents"]


ChunkRuleParams = (
    TokenWindowChunkingParams
    | RecursiveCharacterChunkingParams
    | SemanticChunkingParams
    | PerPageChunkingParams
)


class RagRuntimeService:
    def __init__(
        self,
        repository: RagRepository,
        # embedding_adapter: EmbeddingPort,
        tracer: RuntimeTracerPort,
        rag_policy_service: RagPolicyService,
        ai_repository: AIRepository,
        embedding_executor: EmbeddingExecutor,
    ) -> None:
        self.repository = repository
        # self.embedding_adapter = embedding_adapter
        self.tracer = tracer
        self.rag_policy_service = rag_policy_service
        self.ai_repository = ai_repository
        self.embedding_executor = embedding_executor

    async def _resolve_embedding_model(self, embedding: RagEmbeddingOptions) -> tuple[str, str]:
        if embedding.model_id is not None:
            row = await self.ai_repository.get_model(embedding.model_id)
            if row is None:
                raise NotFoundServiceException(message="embedding_model_not_found")
            if not bool(row.is_active):
                raise DomainValidationException(message="embedding_model_inactive")
            if str(row.type).upper() != "EMBEDDING":
                raise DomainValidationException(
                    message="rag_embedding_model_registry_type_mismatch"
                )
            if row.provider is None or not str(row.provider).strip():
                raise DomainValidationException(
                    message="rag_embedding_model_registry_provider_missing"
                )
            return row.name, str(row.provider).lower()
        row = await self.ai_repository.get_model_by_name(str(embedding.model_alias))
        if row is None:
            raise NotFoundServiceException(message="embedding_model_not_found")
        if not bool(row.is_active):
            raise DomainValidationException(message="embedding_model_inactive")
        if str(row.type).upper() != "EMBEDDING":
            raise DomainValidationException(message="rag_embedding_model_registry_type_mismatch")
        if row.provider is None or not str(row.provider).strip():
            raise DomainValidationException(message="rag_embedding_model_registry_provider_missing")
        return row.name, str(row.provider).lower()

    def _query_embedding_options_for_retrieval(
        self,
        *,
        options: RagConfigOptions,
        vector_store: VectorStoreModel,
    ) -> RagEmbeddingOptions:
        if options.indexing_embedding is None:
            return options.embedding
        if int(vector_store.embedding_dimension) != int(options.indexing_embedding.dimension):
            return options.embedding
        if int(options.embedding.dimension) >= int(vector_store.embedding_dimension):
            return options.embedding
        return options.indexing_embedding.model_copy(
            update={"dimension": options.embedding.dimension}
        )

    def _embedding_contract_from_store(
        self, *, vector_store: VectorStoreModel, provider: str
    ) -> EmbeddingContract:
        return EmbeddingContract(
            provider=provider,
            model=str(vector_store.embedding_model),
            dimension=int(vector_store.embedding_dimension),
            metric=str(vector_store.metric),
            version=int(vector_store.version),
        )

    def _ingest_rag_embedding_options(self, options: RagConfigOptions) -> RagEmbeddingOptions:
        if options.indexing_embedding is not None:
            return options.indexing_embedding
        return options.embedding

    async def ingest_document(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        document: RagDocumentCreate,
    ) -> RagDocument:
        prepared: RagPreparedDocument = await self.prepare_document_for_embedding(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            document=document,
        )
        if prepared.embedding_status == EmbeddingStatus.COMPLETED:
            return RagDocument(
                id=prepared.id,
                source=prepared.source,
                doc_type=prepared.doc_type,
                content_hash=prepared.content_hash,
                metadata=prepared.metadata,
                embedding_status=prepared.embedding_status,
                rag_config_id=document.rag_config_id,
            )
        return await self.embed_document_by_id(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            document_id=prepared.id,
        )

    async def ingest_documents_batch(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        documents: list[RagDocumentCreate],
        max_failures_to_log: int = 20,
    ) -> tuple[int, int]:
        """Ingest multiple RAG documents sequentially."""
        if not documents:
            raise DomainValidationException(message="rag_documents_required")

        succeeded_count = 0
        failed_count = 0
        failures_logged = 0

        for document in documents:
            try:
                await self.ingest_document(
                    tenant_id=tenant_id,
                    rag_config_id=rag_config_id,
                    document=document,
                )
                succeeded_count += 1
            except Exception as exc:
                failed_count += 1
                if failures_logged < max_failures_to_log:
                    failures_logged += 1
                    logger.error(
                        "RAG documents ingestion item failed",
                        rag_config_id=str(rag_config_id),
                        doc_type=str(document.doc_type or ""),
                        error_type=type(exc).__name__,
                    )

        return succeeded_count, failed_count

    async def prepare_document_for_embedding(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        document: RagDocumentCreate,
    ) -> RagPreparedDocument:
        with self.tracer.observe(
            as_type="span",
            name="domain.rag.runtime.prepare_document_for_embedding",
            input={"rag_config_id": str(rag_config_id), "tenant_id": str(tenant_id)},
        ) as span:
            _, rule_params, _, _ = await self._resolve_rag_ingest_bundle(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
            )
            max_chars: int = rule_params.max_document_chars
            if len(document.content) > max_chars:
                raise DomainValidationException(message="rag_document_too_large")
            content_hash = self._hash_text(document.content)
            existing: RagDocument | None = await self.repository.get_document_by_hash(
                tenant_id=tenant_id,
                content_hash=content_hash,
            )
            if existing:
                status = self._as_embedding_status(existing.embedding_status)
                if status != EmbeddingStatus.COMPLETED:
                    await self.repository.update_document_embedding_status(
                        document_id=existing.document_id,
                        status=EmbeddingStatus.PENDING,
                    )
                    status = EmbeddingStatus.PENDING
                return RagPreparedDocument(
                    id=existing.document_id,
                    source=existing.source,
                    doc_type=existing.doc_type,
                    content_hash=existing.content_hash,
                    metadata=existing.doc_metadata,
                    embedding_status=status,
                )
            doc_rag_config_id: UUID = (
                document.rag_config_id if document.rag_config_id is not None else rag_config_id
            )
            doc_meta: dict[str, object] = dict(document.metadata or {})
            if document.doc_type == "tool_catalog":
                doc_meta.setdefault("category", RagCorpusKind.TOOL_CATALOG.value)
            if document.pages is not None:
                doc_meta["ingest_pages"] = list(document.pages)
            created: RagDocument = await self.repository.create_document(
                tenant_id=tenant_id,
                source=document.source,
                doc_type=document.doc_type,
                content_hash=content_hash,
                content=document.content,
                version=document.version,
                metadata=doc_meta,
                embedding_status=EmbeddingStatus.PENDING,
                rag_config_id=doc_rag_config_id,
            )
            prepared_document: RagPreparedDocument = RagPreparedDocument(
                id=created.document_id,
                source=created.source,
                doc_type=created.doc_type,
                content_hash=created.content_hash,
                metadata=created.doc_metadata,
                embedding_status=EmbeddingStatus.PENDING,
            )
            if span:
                span.update(output=prepared_document.model_dump(mode="json"))
            return prepared_document

    async def embed_document_by_id(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        document_id: UUID,
    ) -> RagDocument:
        with self.tracer.observe(
            as_type="span",
            name="domain.rag.runtime.embed_document_by_id",
            input={
                "tenant_id": str(tenant_id),
                "rag_config_id": str(rag_config_id),
                "document_id": str(document_id),
            },
        ) as embedder_handle:
            (
                options,
                rule_params,
                corpus_kind,
                vector_store_id,
            ) = await self._resolve_rag_ingest_bundle(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
            )
            vector_store = await self.repository.get_vector_store(
                vector_store_id, tenant_id=tenant_id
            )
            if vector_store is None:
                embedder_handle.error(
                    error_type="vector_store_not_found",
                    error_message="vector_store_not_found",
                )
                raise NotFoundServiceException(message="vector_store_not_found")
            ingest_embedding = self._ingest_rag_embedding_options(options)
            (
                embedding_model_name,
                embedding_provider,
            ) = await self._resolve_embedding_model(ingest_embedding)
            if embedding_model_name != vector_store.embedding_model:
                raise DomainValidationException(message="rag_embedding_model_vector_store_mismatch")
            if int(ingest_embedding.dimension) != int(vector_store.embedding_dimension):
                raise DomainValidationException(
                    message="rag_embedding_dimension_vector_store_mismatch"
                )
            document = await self.repository.get_document_by_id(document_id=document_id)
            if document is None or document.tenant_id != tenant_id:
                embedder_handle.error(
                    error_type="rag_document_not_found",
                    error_message="rag_document_not_found",
                )
                raise NotFoundServiceException(message="rag_document_not_found")
            current_status = self._as_embedding_status(document.embedding_status)
            if current_status == EmbeddingStatus.COMPLETED:
                embedder_handle.success(output={"embedding_status": EmbeddingStatus.COMPLETED})
                return RagDocument(
                    id=document.document_id,
                    source=document.source,
                    doc_type=document.doc_type,
                    content_hash=document.content_hash,
                    metadata=document.doc_metadata,
                    embedding_status=EmbeddingStatus.COMPLETED,
                    rag_config_id=document.rag_config_id,
                )
            if not isinstance(document.content, str) or not document.content:
                embedder_handle.error(
                    error_type="rag_document_content_required",
                    error_message="rag_document_content_required",
                )
                raise DomainValidationException(message="rag_document_content_required")
            started_at = datetime.now(timezone.utc)
            await self.repository.update_document_embedding_status(
                document_id=document.document_id,
                status=EmbeddingStatus.PROCESSING,
                increment_attempts=True,
                started_at=started_at,
                error_code=None,
            )
            raw_meta = document.doc_metadata or {}
            ingest_pages: list[str] | None = None
            raw_pages = raw_meta.get("ingest_pages")
            if raw_pages is not None and type(raw_pages) is list:
                ingest_pages = [str(x) for x in raw_pages]
            chunks, truncated = self._chunks_for_ingest(
                content=document.content,
                rule_params=rule_params,
                ingest_pages=ingest_pages,
            )
            document_metadata = dict(raw_meta)
            if truncated:
                document_metadata["truncated"] = True
                document_metadata["truncated_chunks"] = len(chunks)
            try:
                resolved_policy: ResolvedRagPolicy = await self.rag_policy_service.resolve(
                    tenant_id=tenant_id
                )
                quotas: RagIngestQuotas | None = None
                if resolved_policy.definition is not None:
                    quotas = resolved_policy.definition.ingest_quotas
                contract = self._embedding_contract_from_store(
                    vector_store=vector_store,
                    provider=embedding_provider,
                )
                embeddings = await self.embedding_executor.execute_batch(
                    EmbeddingBatchExecutionRequest(
                        texts=chunks,
                        contract=contract,
                        use_case="indexing",
                    )
                )
                chunk_models: list[RagChunkModel] = []
                for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_models.append(
                        RagChunkModel(
                            chunk_id=uuid4(),
                            document_id=document.document_id,
                            vector_store_id=vector_store_id,
                            chunk_index=idx,
                            content=chunk_text,
                            content_hash=self._hash_text(chunk_text),
                            token_count=len(self._encode_tokens(chunk_text)),
                            embedding=embedding,
                            chunk_metadata=document_metadata,
                        )
                    )
                completed_at = datetime.now(timezone.utc)
                await self.repository.finalize_document_embedding_with_usage(
                    tenant_id=tenant_id,
                    rag_config_id=rag_config_id,
                    corpus_kind=corpus_kind,
                    document_id=document.document_id,
                    chunks=chunk_models,
                    completed_at=completed_at,
                    quotas=quotas,
                )
                embedder_handle.success(
                    output={
                        "embedding_status": EmbeddingStatus.COMPLETED,
                        "completed_at": completed_at,
                        "document_id": document.document_id,
                    }
                )
            except Exception as exc:
                await self.repository.update_document_embedding_status(
                    document_id=document.document_id,
                    status=EmbeddingStatus.FAILED,
                    error_code=exc.__class__.__name__,
                    completed_at=datetime.now(timezone.utc),
                )
                raise exc from exc
            return RagDocument(
                id=document.document_id,
                source=document.source,
                doc_type=document.doc_type,
                content_hash=document.content_hash,
                metadata=document.doc_metadata,
                embedding_status=EmbeddingStatus.COMPLETED,
                rag_config_id=document.rag_config_id,
            )

    async def list_documents(
        self,
        *,
        tenant_id: UUID,
        limit: int,
        rag_config_id: UUID | None = None,
    ) -> list[RagDocument]:
        """List documents available for a tenant, optionally filtered by rag_config_id."""
        items = await self.repository.list_documents(
            tenant_id=tenant_id, limit=limit, rag_config_id=rag_config_id
        )
        return [
            RagDocument(
                id=item.document_id,
                source=item.source,
                doc_type=item.doc_type,
                content_hash=item.content_hash,
                metadata=item.doc_metadata,
                embedding_status=self._as_embedding_status(item.embedding_status),
                rag_config_id=item.rag_config_id,
            )
            for item in items
        ]

    async def reindex_cutover_vector_store(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        target_vector_store_id: UUID,
    ) -> None:
        config = await self.repository.get_rag_config(rag_config_id)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")
        current_vector_store_id = config.vector_store_id
        if current_vector_store_id == target_vector_store_id:
            return
        in_progress_count = await self.repository.count_documents_by_embedding_status(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            statuses=[
                EmbeddingStatus.PENDING.value,
                EmbeddingStatus.PROCESSING.value,
            ],
        )
        if in_progress_count > 0:
            raise DomainValidationException(message="rag_reindex_cutover_in_progress_documents")
        current_store = await self.repository.get_vector_store(
            current_vector_store_id, tenant_id=tenant_id
        )
        target_store = await self.repository.get_vector_store(
            target_vector_store_id, tenant_id=tenant_id
        )
        if current_store is None or target_store is None:
            raise NotFoundServiceException(message="vector_store_not_found")
        await self.repository.update_rag_config_vector_store(
            rag_config_id=rag_config_id,
            tenant_id=tenant_id,
            vector_store_id=target_vector_store_id,
        )
        await self.repository.set_vector_store_active(
            vector_store_id=current_vector_store_id,
            tenant_id=tenant_id,
            active=False,
        )
        await self.repository.set_vector_store_active(
            vector_store_id=target_vector_store_id,
            tenant_id=tenant_id,
            active=True,
        )
        await self.repository.invalidate_query_cache_vector_store(
            tenant_id=tenant_id,
            vector_store_id=current_vector_store_id,
        )
        await self.repository.invalidate_query_cache_vector_store(
            tenant_id=tenant_id,
            vector_store_id=target_vector_store_id,
        )

    async def count_documents_for_user(self, *, tenant_id: UUID, user_id: str) -> int:
        return await self.repository.count_documents_for_user(tenant_id=tenant_id, user_id=user_id)

    async def count_user_memory_documents_for_rag_config(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        rag_config_id: UUID,
    ) -> int:
        return await self.repository.count_user_memory_documents_for_rag_config(
            tenant_id=tenant_id,
            user_id=user_id,
            rag_config_id=rag_config_id,
        )

    async def resolve_user_memory_vector_document_cap(
        self, *, tenant_id: UUID
    ) -> UserMemoryVectorDocumentCap:
        app_max = int(settings.MAX_USER_MEMORY_DOCUMENTS)
        resolved = await self.rag_policy_service.resolve(tenant_id=tenant_id)
        tenant_q: int | None = None
        definition = resolved.definition
        if definition is not None and definition.ingest_quotas is not None:
            raw = definition.ingest_quotas.max_documents_per_user
            if raw is not None:
                tenant_q = int(raw)
        if tenant_q is None:
            return UserMemoryVectorDocumentCap(
                effective_cap=app_max,
                app_max_user_memory_documents=app_max,
                tenant_max_documents_per_user=None,
                binding="app",
                reason_code="app_max_user_memory_documents",
            )
        if tenant_q < app_max:
            return UserMemoryVectorDocumentCap(
                effective_cap=tenant_q,
                app_max_user_memory_documents=app_max,
                tenant_max_documents_per_user=tenant_q,
                binding="rag_policy",
                reason_code="rag_ingest_quota_user_documents",
            )
        return UserMemoryVectorDocumentCap(
            effective_cap=app_max,
            app_max_user_memory_documents=app_max,
            tenant_max_documents_per_user=tenant_q,
            binding="app",
            reason_code="app_max_user_memory_documents",
        )

    async def list_chunks(self, *, document_id: UUID, limit: int) -> list[RagChunk]:
        """List chunks for a stored document."""
        items = await self.repository.list_chunks(document_id=document_id, limit=limit)
        return [
            RagChunk(
                id=item.chunk_id,
                document_id=item.document_id,
                vector_store_id=item.vector_store_id,
                chunk_index=item.chunk_index,
                content=item.content,
                metadata=item.chunk_metadata,
            )
            for item in items
        ]

    async def get_context(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        user_id: str | None = None,
        user_input: str,
        filters_override: dict[str, object] | None = None,
        top_k_override: int | None = None,
        similarity_threshold_cap: float | None = None,
    ) -> RagContext:
        """Retrieve eligible context for a user query."""

        config = await self.repository.get_rag_config(rag_config_id)

        if config is None or config.tenant_id != tenant_id:
            return RagContext(
                context_items=[],
                context_summary=None,
                eligible=False,
                reason=RagContextReason.CONFIG_NOT_FOUND,
                generation_contract=None,
            )

        options: RagConfigOptions = RagConfigOptions.model_validate(config.options or {})
        if options.embedding.dimension not in SUPPORTED_EMBEDDING_DIMENSIONS:
            raise DomainValidationException(message="rag_embedding_dimension_not_supported")
        vector_store = await self.repository.get_vector_store(
            config.vector_store_id, tenant_id=tenant_id
        )
        if vector_store is None:
            return RagContext(
                context_items=[],
                context_summary=None,
                eligible=False,
                reason=RagContextReason.CONFIG_NOT_FOUND,
                generation_contract=None,
            )
        if not options.embedding:
            raise DomainValidationException(message="rag_retrievel_embedding_not_found")

        if int(options.embedding.dimension) > int(vector_store.embedding_dimension):
            raise DomainValidationException(
                message="rag_retrieval_embedding_dimension_vector_store_mismatch"
            )

        query_opts = self._query_embedding_options_for_retrieval(
            options=options,
            vector_store=vector_store,
        )
        resolved_model, provider = await self._resolve_embedding_model(query_opts)
        embedding_contract = EmbeddingContract(
            provider=provider,
            model=resolved_model,
            dimension=int(query_opts.dimension),
            metric=str(vector_store.metric),
            version=int(vector_store.version),
        )

        query_hash: str = self._hash_text(user_input)
        await self.repository.invalidate_query_cache_contract(
            tenant_id=tenant_id,
            vector_store_id=config.vector_store_id,
            contract_hash=embedding_contract.contract_hash,
        )
        cached: RagQueryCacheModel | None = await self.repository.get_query_cache(
            tenant_id=tenant_id,
            vector_store_id=config.vector_store_id,
            vector_store_version=embedding_contract.version,
            contract_hash=embedding_contract.contract_hash,
            query_hash=query_hash,
        )
        if cached is not None and cached.embedding is not None:
            embedding = self._query_cache_embedding_to_list(cached.embedding)
            await self.repository.update_query_cache_usage(cache_id=cached.query_cache_id)
        else:
            embedding = await self.embedding_executor.execute(
                EmbeddingExecutionRequest(
                    text=user_input,
                    contract=embedding_contract,
                    use_case="retrieval",
                    allow_fallback=False,
                )
            )
            cache_entry = RagQueryCacheModel(
                tenant_id=tenant_id,
                vector_store_id=config.vector_store_id,
                vector_store_version=embedding_contract.version,
                contract_hash=embedding_contract.contract_hash,
                query_hash=query_hash,
                embedding=embedding,
            )
            await self.repository.save_query_cache(cache_entry=cache_entry)

        effective_filters: dict = dict(options.retrieval.filters or {})
        if filters_override:
            effective_filters.update(filters_override)
        effective_top_k = int(options.retrieval.top_k)
        if top_k_override is not None:
            effective_top_k = max(1, int(top_k_override))
        effective_similarity_threshold = float(options.retrieval.similarity_threshold)
        if similarity_threshold_cap is not None:
            effective_similarity_threshold = min(
                effective_similarity_threshold, float(similarity_threshold_cap)
            )
        results: list[
            tuple[RagChunkModel, float, datetime | None, str | None]
        ] = await self.repository.search_similar_chunks(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            vector_store_id=config.vector_store_id,
            user_id=user_id,
            query_embedding=embedding,
            top_k=effective_top_k,
            similarity_threshold=effective_similarity_threshold,
            filters=effective_filters,
        )
        if not results:
            return RagContext(
                context_items=[],
                context_summary=None,
                eligible=False,
                reason=RagContextReason.NO_MATCHES,
                generation_contract=options.generation_contract,
            )

        items: list[RagContextItem] = []
        for chunk, score, document_created_at, document_observed_at in results:
            observed_at = self._parse_datetime(document_observed_at)
            items.append(
                RagContextItem(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    score=score,
                    metadata=chunk.chunk_metadata,
                    created_at=document_created_at,
                    observed_at=observed_at,
                )
            )
        return RagContext(
            context_items=items,
            context_summary=None,
            eligible=True,
            reason=RagContextReason.OK,
            generation_contract=options.generation_contract,
        )

    def _encode_tokens(self, text: str) -> list[int]:
        encoder = tiktoken.get_encoding("cl100k_base")
        return encoder.encode(text)

    async def _resolve_rag_ingest_bundle(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
    ) -> tuple[RagConfigOptions, ChunkRuleParams, str, UUID]:
        config = await self.repository.get_rag_config(rag_config_id)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")
        rule = await self.repository.get_chunking_rule(
            tenant_id=tenant_id,
            rag_chunking_rule_id=config.chunking_rule_id,
        )
        if rule is None:
            raise NotFoundServiceException(message="rag_chunking_rule_not_found")
        rule_params = parse_rag_chunking_rule_params(rule.params or {})
        options = RagConfigOptions.model_validate(config.options or {})
        if options.embedding.dimension not in SUPPORTED_EMBEDDING_DIMENSIONS:
            raise DomainValidationException(message="rag_embedding_dimension_not_supported")
        if options.indexing_embedding is not None:
            if options.indexing_embedding.dimension not in SUPPORTED_EMBEDDING_DIMENSIONS:
                raise DomainValidationException(message="rag_embedding_dimension_not_supported")
        return options, rule_params, config.corpus_kind, config.vector_store_id

    def _chunks_for_ingest(
        self,
        *,
        content: str,
        rule_params: ChunkRuleParams,
        ingest_pages: list[str] | None,
    ) -> tuple[list[str], bool]:
        strat = rule_params.strategy
        if strat == RagChunkingStrategy.PER_PAGE:
            pages = ingest_pages
            if pages is None or len(pages) == 0:
                raise DomainValidationException(
                    message="rag_per_page_pages_required",
                    name="RAG_PER_PAGE_PAGES_REQUIRED",  # Todo: Why here don't have a StrEnum ?
                    input_data={"code": "rag_per_page_pages_required"},
                    status_code=422,
                )
            out: list[str] = []
            for raw in pages[: rule_params.max_chunks_per_document]:
                piece = (
                    raw
                    if len(raw) <= rule_params.max_document_chars
                    else raw[: rule_params.max_document_chars]
                )
                if piece:
                    out.append(piece)
            truncated = len(pages) > rule_params.max_chunks_per_document or any(
                len(p) > rule_params.max_document_chars for p in pages
            )
            return out, truncated
        if strat == RagChunkingStrategy.TOKEN_WINDOW:
            return self._chunk_text(
                content,
                rule_params.target_tokens,
                rule_params.overlap_tokens,
                rule_params.max_chunks_per_document,
            )
        if strat == RagChunkingStrategy.SEMANTIC:
            return self._chunk_text(
                content,
                rule_params.target_tokens,
                rule_params.overlap_tokens,
                rule_params.max_chunks_per_document,
            )
        if strat == RagChunkingStrategy.RECURSIVE_CHARACTER:
            return self._recursive_character_chunks(
                content,
                rule_params.chunk_size,
                rule_params.chunk_overlap,
                rule_params.max_chunks_per_document,
                rule_params.separators,
            )
        raise DomainValidationException(message="rag_chunking_strategy_unsupported")

    def _recursive_character_chunks(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        max_chunks: int,
        separators: list[str],
    ) -> tuple[list[str], bool]:
        if len(text) <= chunk_size:
            return [text], False
        parts: list[str] = []
        idx = 0
        while idx < len(text) and len(parts) < max_chunks:
            window = text[idx : idx + chunk_size]
            if len(window) < chunk_size:
                tail = window.strip()
                if tail:
                    parts.append(tail)
                break
            cut = len(window)
            for sep in separators:
                if sep == "":
                    continue
                pos = window.rfind(sep)
                if pos >= chunk_size // 2:
                    cut = pos + len(sep)
                    break
            segment = text[idx : idx + cut].strip()
            if segment:
                parts.append(segment)
            nxt = idx + cut - chunk_overlap
            idx = nxt if nxt > idx else idx + cut
        truncated = idx < len(text) and len(parts) >= max_chunks
        return parts, truncated

    def _chunk_text(
        self,
        text: str,
        target_tokens: int,
        overlap_tokens: int,
        max_chunks: int,
    ) -> tuple[list[str], bool]:
        tokens = self._encode_tokens(text)
        if len(tokens) <= target_tokens:
            return [text], False
        encoder = tiktoken.get_encoding("cl100k_base")
        step = max(1, target_tokens - overlap_tokens)
        chunks: list[str] = []
        start = 0
        truncated = False
        while start < len(tokens):
            if len(chunks) >= max_chunks:
                truncated = True
                break
            end = min(start + target_tokens, len(tokens))
            chunks.append(encoder.decode(tokens[start:end]))
            if end >= len(tokens):
                break
            start += step
        return chunks, truncated

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _as_embedding_status(self, value: str | None) -> EmbeddingStatus:
        if value is None:
            return EmbeddingStatus.PENDING
        try:
            return EmbeddingStatus(value)
        except ValueError:
            return EmbeddingStatus.PENDING

    @staticmethod
    def _query_cache_embedding_to_list(raw: object | None) -> list[float]:
        if raw is None:
            return []
        if isinstance(raw, np.ndarray):
            return raw.tolist()
        try:
            return np.asarray(raw, dtype=float).tolist()
        except Exception:
            logger.warning("Failed to convert query cache embedding to list")
            return []
