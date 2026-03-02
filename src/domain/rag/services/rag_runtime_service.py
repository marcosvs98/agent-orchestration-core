from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

import tiktoken

from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.embedding_job import EmbeddingStatus
from domain.rag.schemas.rag import (
    RagConfigOptions,
    RagContext,
    RagContextReason,
    RagContextItem,
    RagDocument,
    RagDocumentCreate,
    RagChunk,
    RagPreparedDocument,
)
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database.models.rag.rag_chunk import RagChunk as RagChunkModel
from infra.database.models.rag.rag_query_cache import (
    RagQueryCache as RagQueryCacheModel,
)


class RagRuntimeService:
    """Provide ingestion and retrieval capabilities for RAG at runtime."""

    def __init__(
        self,
        repository: RagRepository,
        embedding_adapter: OpenAIEmbeddingAdapter,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.repository = repository
        self.embedding_adapter = embedding_adapter
        self.tracer = tracer

    async def ingest_document(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        document: RagDocumentCreate,
    ) -> RagDocument:
        prepared = await self.prepare_document_for_embedding(
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
            )
        return await self.embed_document_by_id(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            document_id=prepared.id,
        )

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
        ):
            options = await self._resolve_rag_options(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
            )
            if len(document.content) > options.chunking.max_document_chars:
                raise DomainValidationException(message="rag_document_too_large")
            content_hash = self._hash_text(document.content)
            existing = await self.repository.get_document_by_hash(
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
            created = await self.repository.create_document(
                tenant_id=tenant_id,
                source=document.source,
                doc_type=document.doc_type,
                content_hash=content_hash,
                content=document.content,
                version=document.version,
                metadata=document.metadata,
                embedding_status=EmbeddingStatus.PENDING,
            )
            return RagPreparedDocument(
                id=created.document_id,
                source=created.source,
                doc_type=created.doc_type,
                content_hash=created.content_hash,
                metadata=created.doc_metadata,
                embedding_status=EmbeddingStatus.PENDING,
            )

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
            options = await self._resolve_rag_options(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
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
                embedder_handle.success(
                    output={"embedding_status": EmbeddingStatus.COMPLETED}
                )
                return RagDocument(
                    id=document.document_id,
                    source=document.source,
                    doc_type=document.doc_type,
                    content_hash=document.content_hash,
                    metadata=document.doc_metadata,
                    embedding_status=EmbeddingStatus.COMPLETED,
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
            chunks, truncated = self._chunk_text(
                document.content,
                options.chunking.target_tokens,
                options.chunking.overlap_tokens,
                options.chunking.max_chunks_per_document,
            )
            document_metadata = dict(document.doc_metadata or {})
            if truncated:
                document_metadata["truncated"] = True
                document_metadata["truncated_chunks"] = len(chunks)
            try:
                embeddings = await self.embedding_adapter.generate_embeddings_batch(
                    chunks,
                    model=options.embedding.model_alias,
                    dimension=options.embedding.dimension,
                )
                chunk_models: list[RagChunkModel] = []
                for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_models.append(
                        RagChunkModel(
                            chunk_id=uuid4(),
                            document_id=document.document_id,
                            chunk_index=idx,
                            content=chunk_text,
                            content_hash=self._hash_text(chunk_text),
                            token_count=len(self._encode_tokens(chunk_text)),
                            embedding=embedding,
                            embedding_model=options.embedding.model_alias,
                            embedding_dimension=options.embedding.dimension,
                            chunk_metadata=document_metadata,
                        )
                    )
                await self.repository.create_chunks(chunks=chunk_models)
                completed_at = datetime.now(timezone.utc)
                await self.repository.update_document_embedding_status(
                    document_id=document.document_id,
                    status=EmbeddingStatus.COMPLETED,
                    completed_at=completed_at,
                    error_code=None,
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
                raise
            return RagDocument(
                id=document.document_id,
                source=document.source,
                doc_type=document.doc_type,
                content_hash=document.content_hash,
                metadata=document.doc_metadata,
                embedding_status=EmbeddingStatus.COMPLETED,
            )

    async def list_documents(self, *, tenant_id: UUID, limit: int) -> list[RagDocument]:
        """List documents available for a tenant."""
        items = await self.repository.list_documents(tenant_id=tenant_id, limit=limit)
        return [
            RagDocument(
                id=item.document_id,
                source=item.source,
                doc_type=item.doc_type,
                content_hash=item.content_hash,
                metadata=item.doc_metadata,
                embedding_status=self._as_embedding_status(item.embedding_status),
            )
            for item in items
        ]

    async def count_documents_for_user(self, *, tenant_id: UUID, user_id: str) -> int:
        return await self.repository.count_documents_for_user(
            tenant_id=tenant_id, user_id=user_id
        )

    async def list_chunks(self, *, document_id: UUID, limit: int) -> list[RagChunk]:
        """List chunks for a stored document."""
        items = await self.repository.list_chunks(document_id=document_id, limit=limit)
        return [
            RagChunk(
                id=item.chunk_id,
                document_id=item.document_id,
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

        options = RagConfigOptions.model_validate(config.options or {})
        if options.embedding.dimension != 1536: # Todo: Criar env em settings
            raise DomainValidationException(
                message="rag_embedding_dimension_not_supported"
            )
        query_hash = self._hash_text(user_input)
        cached = await self.repository.get_query_cache(
            tenant_id=tenant_id, query_hash=query_hash
        )
        embedding: list[float]
        if (
            cached
            and cached.embedding_model == options.embedding.model_alias
            and cached.embedding_dimension == options.embedding.dimension
        ):
            embedding = cached.embedding
            await self.repository.update_query_cache_usage(
                cache_id=cached.query_cache_id
            )
        else:
            embedding = await self.embedding_adapter.generate_embedding(
                user_input,
                model=options.embedding.model_alias,
                dimension=options.embedding.dimension,
            )
            cache_entry = RagQueryCacheModel(
                tenant_id=tenant_id,
                query_hash=query_hash,
                embedding=embedding,
                embedding_model=options.embedding.model_alias,
                embedding_dimension=options.embedding.dimension,
            )
            await self.repository.save_query_cache(cache_entry=cache_entry)

        effective_filters = dict(options.retrieval.filters or {})
        if filters_override:
            effective_filters.update(filters_override)
        effective_top_k = int(options.retrieval.top_k)
        if top_k_override is not None:
            effective_top_k = max(1, int(top_k_override))
        with self.tracer.observe(
            as_type="retriever",
            name="domain.rag.runtime.search_similar_chunks",
            input={
                "tenant_id": str(tenant_id),
                "top_k": effective_top_k,
                "similarity_threshold": options.retrieval.similarity_threshold,
            },
        ) as retriever_handle:
            results = await self.repository.search_similar_chunks(
                tenant_id=tenant_id,
                user_id=user_id,
                query_embedding=embedding,
                top_k=effective_top_k,
                similarity_threshold=options.retrieval.similarity_threshold,
                filters=effective_filters,
            )
            retriever_handle.success(output={"chunk_count": len(results)})
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
        chunks: list[str] = []
        start = 0
        while start < len(tokens) and len(chunks) < max_chunks:
            end = min(start + target_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = tiktoken.get_encoding("cl100k_base").decode(chunk_tokens)
            chunks.append(chunk_text)
            start = end - overlap_tokens
            if start < 0:  # pylint: disable=consider-using-max-builtin
                start = 0
            if start >= len(tokens):
                break
        truncated = len(chunks) >= max_chunks and start < len(tokens)
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

    async def _resolve_rag_options(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
    ) -> RagConfigOptions:
        config = await self.repository.get_rag_config(rag_config_id)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")
        options = RagConfigOptions.model_validate(config.options or {})
        if options.embedding.dimension != 1536:
            raise DomainValidationException(
                message="rag_embedding_dimension_not_supported"
            )
        return options
