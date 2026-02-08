from __future__ import annotations

import hashlib
from typing import Iterable
from uuid import UUID

import tiktoken

from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import (
    RagConfigOptions,
    RagContext,
    RagContextItem,
    RagDocument,
    RagDocumentCreate,
    RagChunk,
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
        """Ingest a document into the RAG store."""
        with self.tracer.observe(
            as_type="span",
            name="domain.rag.runtime.ingest_document",
            input={"rag_config_id": str(rag_config_id), "tenant_id": str(tenant_id)},
        ):
            config = await self.repository.get_rag_config(rag_config_id)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")

        options = RagConfigOptions.model_validate(config.options or {})
        if options.embedding.dimension != 1536:
            raise DomainValidationException(
                message="rag_embedding_dimension_not_supported"
            )
        if len(document.content) > options.chunking.max_document_chars:
            raise DomainValidationException(message="rag_document_too_large")

        content_hash = self._hash_text(document.content)
        existing = await self.repository.get_document_by_hash(
            tenant_id=tenant_id, content_hash=content_hash
        )
        if existing:
            return RagDocument(
                id=existing.document_id,
                source=existing.source,
                doc_type=existing.doc_type,
                content_hash=existing.content_hash,
                metadata=existing.doc_metadata,
            )

        chunks, truncated = self._chunk_text(
            document.content,
            options.chunking.target_tokens,
            options.chunking.overlap_tokens,
            options.chunking.max_chunks_per_document,
        )
        document_metadata = dict(document.metadata or {})
        if truncated:
            document_metadata["truncated"] = True
            document_metadata["truncated_chunks"] = len(chunks)
        created = await self.repository.create_document(
            tenant_id=tenant_id,
            source=document.source,
            doc_type=document.doc_type,
            content_hash=content_hash,
            content=document.content,
            version=document.version,
            metadata=document_metadata,
        )

        embeddings = await self.embedding_adapter.generate_embeddings_batch(
            chunks,
            model=options.embedding.model_alias,
            dimension=options.embedding.dimension,
        )
        chunk_models: list[RagChunkModel] = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_models.append(
                RagChunkModel(
                    document_id=created.document_id,
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

        return RagDocument(
            id=created.document_id,
            source=created.source,
            doc_type=created.doc_type,
            content_hash=created.content_hash,
            metadata=created.doc_metadata,
        )

    async def list_documents(
        self, *, tenant_id: UUID, limit: int
    ) -> list[RagDocument]:
        """List documents available for a tenant."""
        items = await self.repository.list_documents(tenant_id=tenant_id, limit=limit)
        return [
            RagDocument(
                id=item.document_id,
                source=item.source,
                doc_type=item.doc_type,
                content_hash=item.content_hash,
                metadata=item.doc_metadata,
            )
            for item in items
        ]

    async def list_chunks(
        self, *, document_id: UUID, limit: int
    ) -> list[RagChunk]:
        """List chunks for a stored document."""
        items = await self.repository.list_chunks(
            document_id=document_id, limit=limit
        )
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
        user_input: str,
    ) -> RagContext:
        """Retrieve eligible context for a user query."""
        with self.tracer.observe(
            as_type="retriever",
            name="domain.rag.runtime.get_context",
            input={"rag_config_id": str(rag_config_id), "tenant_id": str(tenant_id)},
        ):
            config = await self.repository.get_rag_config(rag_config_id)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")

        options = RagConfigOptions.model_validate(config.options or {})
        if options.embedding.dimension != 1536:
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
            await self.repository.update_query_cache_usage(cache_id=cached.query_cache_id)
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

        results = await self.repository.search_similar_chunks(
            tenant_id=tenant_id,
            query_embedding=embedding,
            top_k=options.retrieval.top_k,
            similarity_threshold=options.retrieval.similarity_threshold,
            filters=options.retrieval.filters,
        )
        if not results:
            return RagContext(
                context_items=[],
                context_summary=None,
                eligible=False,
                reason="NO_MATCHES",
                generation_contract=options.generation_contract,
            )

        items = [
            RagContextItem(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=score,
                metadata=chunk.chunk_metadata,
            )
            for chunk, score in results
        ]
        avg_score = sum(item.score for item in items) / len(items)
        with self.tracer.observe(
            as_type="evaluator",
            name="domain.rag.runtime.evaluate_relevance",
            input={
                "rag_config_id": str(rag_config_id),
                "avg_score": avg_score,
                "item_count": len(items),
            },
        ):
            if avg_score < options.retrieval.similarity_threshold + 0.05:

                return RagContext(
                    context_items=[],
                    context_summary=None,
                    eligible=False,
                    reason="LOW_RELEVANCE",
                    generation_contract=options.generation_contract,
                )
        return RagContext(
            context_items=items,
            context_summary=None,
            eligible=True,
            reason="OK",
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
            if start < 0:
                start = 0
            if start >= len(tokens):
                break
        truncated = len(chunks) >= max_chunks and start < len(tokens)
        return chunks, truncated

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
