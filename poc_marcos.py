# embedding_service.py
from typing import Optional
from sqlalchemy import select, and_, update
from datetime import datetime

from infra.database import DatabaseConnection
from infra.database.models.rag.embedding_version import EmbeddingVersion
from adapters.observability.logging import get_logger

logger = get_logger()


class EmbeddingVersionService:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.database_connection = database_connection

    async def get_active_version(
        self, model_provider: str, model_name: str
    ) -> Optional[EmbeddingVersion]:
        async with self.database_connection.get_session() as session:
            result = await session.execute(
                select(EmbeddingVersion)
                .where(
                    and_(
                        EmbeddingVersion.model_provider == model_provider,
                        EmbeddingVersion.model_name == model_name,
                        EmbeddingVersion.is_active,
                    )
                )
                .order_by(EmbeddingVersion.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_default_version(self) -> Optional[EmbeddingVersion]:
        async with self.database_connection.get_session() as session:
            result = await session.execute(
                select(EmbeddingVersion)
                .where(EmbeddingVersion.is_default)
                .order_by(EmbeddingVersion.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def create_version(
        self,
        model_provider: str,
        model_name: str,
        dimension: int,
        version: str,
        config: dict,
        set_as_default: bool = False,
    ) -> EmbeddingVersion:
        async with self.database_connection.get_session() as session:
            if set_as_default:
                await session.execute(update(EmbeddingVersion).values(is_default=False))

            embedding_version = EmbeddingVersion(
                model_provider=model_provider,
                model_name=model_name,
                dimension=dimension,
                version=version,
                is_active=True,
                is_default=set_as_default,
                config=config,
            )

            session.add(embedding_version)
            await session.flush()
            await session.refresh(embedding_version)

            logger.info(
                "Embedding version created",
                version_id=str(embedding_version.id),
                model_provider=model_provider,
                model_name=model_name,
                version=version,
                is_default=set_as_default,
            )

            return embedding_version

    async def deprecate_version(self, version_id) -> None:
        async with self.database_connection.get_session() as session:
            await session.execute(
                update(EmbeddingVersion)
                .where(EmbeddingVersion.id == version_id)
                .values(is_active=False, deprecated_at=datetime.utcnow())
            )

            logger.info("Embedding version deprecated", version_id=str(version_id))

# reindexation_policy
from datetime import datetime

from infra.database.models.rag.embedding_version import EmbeddingVersion
from services.rag.reindexation_service import ReindexationService
from adapters.observability.logging import get_logger

logger = get_logger()


class ReindexationPolicy:
    def __init__(self, reindexation_service: ReindexationService) -> None:
        self.reindexation_service = reindexation_service

    async def evaluate_reindexation_need(
        self,
        old_version: EmbeddingVersion,
        new_version: EmbeddingVersion,
        force: bool = False,
    ) -> dict:
        if force:
            return {
                "should_reindex": True,
                "reason": "force_reindexation",
                "priority": "high",
            }

        if old_version.dimension != new_version.dimension:
            return {
                "should_reindex": True,
                "reason": "dimension_mismatch",
                "priority": "critical",
            }

        if old_version.model_name != new_version.model_name:
            return {
                "should_reindex": True,
                "reason": "model_change",
                "priority": "high",
            }

        if old_version.model_provider != new_version.model_provider:
            return {
                "should_reindex": True,
                "reason": "provider_change",
                "priority": "high",
            }

        stats = await self.reindexation_service.get_reindexation_stats(old_version.id)
        if stats["completion_percentage"] < 100.0:
            return {
                "should_reindex": True,
                "reason": "incomplete_indexation",
                "priority": "medium",
                "stats": stats,
            }

        if old_version.deprecated_at:
            days_since_deprecation = (
                datetime.utcnow() - old_version.deprecated_at
            ).days
            if days_since_deprecation > 30:
                return {
                    "should_reindex": True,
                    "reason": "deprecated_version_cleanup",
                    "priority": "low",
                }

        return {"should_reindex": False, "reason": "no_reindexation_needed"}

# reindexation_service.py

from typing import List
from uuid import UUID
from sqlalchemy import select, func, and_

from infra.database import DatabaseConnection
from infra.database.models.rag.chunk import Chunk
from adapters.observability.logging import get_logger

logger = get_logger()


class ReindexationService:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.database_connection = database_connection

    async def should_reindex(
        self, embedding_version_id: UUID, content_hash: str
    ) -> bool:
        async with self.database_connection.get_session() as session:
            result = await session.execute(
                select(func.count(Chunk.id)).where(
                    and_(
                        Chunk.content_hash == content_hash,
                        Chunk.embedding_version_id == embedding_version_id,
                        Chunk.embedding.isnot(None),
                    )
                )
            )
            count = result.scalar() or 0
            return count == 0

    async def get_chunks_needing_reindex(
        self, old_version_id: UUID, new_version_id: UUID, limit: int = 1000
    ) -> List[Chunk]:
        async with self.database_connection.get_session() as session:
            result = await session.execute(
                select(Chunk)
                .where(
                    and_(
                        Chunk.embedding_version_id == old_version_id,
                        Chunk.embedding.isnot(None),
                    )
                )
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_reindexation_stats(self, embedding_version_id: UUID) -> dict:
        async with self.database_connection.get_session() as session:
            total_result = await session.execute(
                select(func.count(Chunk.id)).where(
                    Chunk.embedding_version_id == embedding_version_id
                )
            )
            total_chunks = total_result.scalar() or 0

            indexed_result = await session.execute(
                select(func.count(Chunk.id)).where(
                    and_(
                        Chunk.embedding_version_id == embedding_version_id,
                        Chunk.embedding.isnot(None),
                    )
                )
            )
            indexed_chunks = indexed_result.scalar() or 0

            pending_chunks = total_chunks - indexed_chunks
            completion_percentage = (
                (indexed_chunks / total_chunks * 100) if total_chunks > 0 else 0.0
            )

            return {
                "total_chunks": total_chunks,
                "indexed_chunks": indexed_chunks,
                "pending_chunks": pending_chunks,
                "completion_percentage": completion_percentage,
            }

# chunk_adapter.py

from typing import List
from dataclasses import dataclass


@dataclass
class ChunkData:
    content: str
    token_count: int
    metadata: dict


class ChunkingAdapter:
    def __init__(self, tokenizer) -> None:
        self.tokenizer = tokenizer

    def chunk_text(
        self, text: str, target_tokens: int = 500, overlap_tokens: int = 50
    ) -> List[ChunkData]:
        tokens = self.tokenizer.encode(text)

        if len(tokens) <= target_tokens:
            token_count = len(tokens)
            return [
                ChunkData(
                    content=text, token_count=token_count, metadata={"chunk_index": 0}
                )
            ]

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(tokens):
            end = min(start + target_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)

            chunks.append(
                ChunkData(
                    content=chunk_text,
                    token_count=len(chunk_tokens),
                    metadata={"chunk_index": chunk_index},
                )
            )

            start = end - overlap_tokens
            chunk_index += 1

            if start >= len(tokens):
                break

        return chunks

# rag_repository.py
from typing import Optional
from uuid import UUID
from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload
from datetime import datetime

from infra.database import DatabaseConnection
from infra.database.models.rag.chunk import Chunk
from infra.database.models.rag.document import Document
from infra.database.models.rag.embedding_version import EmbeddingVersion
from infra.database.models.rag.query_cache import QueryCache
from adapters.observability.logging import get_logger
from langfuse import Langfuse
import structlog
from utils.query_compiler import compile_query

logger = get_logger()


class RAGRepository:
    def __init__(self, database_connection: DatabaseConnection, langfuse: Langfuse):
        self.database_connection = database_connection
        self.langfuse = langfuse

    async def get_chunk_by_id(self, chunk_id: UUID) -> Optional[Chunk]:
        async with self.database_connection.get_session() as session:
            stmt = select(Chunk).where(Chunk.id == chunk_id)
            query_sql = compile_query(stmt)

            with self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.repository.get_chunk_by_id",
                metadata=structlog.contextvars.get_contextvars(),
            ) as retriever_span:
                retriever_span.update(input={"query": query_sql})

                result = await session.execute(stmt)
                chunk = result.scalar_one_or_none()

                result_count = 1 if chunk else 0
                retriever_span.update(
                    output={"result_count": result_count, "found": chunk is not None}
                )

                return chunk

    async def get_document_by_id(self, document_id: UUID) -> Optional[Document]:
        async with self.database_connection.get_session() as session:
            stmt = (
                select(Document)
                .where(Document.id == document_id)
                .options(selectinload(Document.chunks))
            )
            query_sql = compile_query(stmt)

            with self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.repository.get_document_by_id",
                metadata=structlog.contextvars.get_contextvars(),
            ) as retriever_span:
                retriever_span.update(input={"query": query_sql})

                result = await session.execute(stmt)
                document = result.scalar_one_or_none()

                result_count = 1 if document else 0
                retriever_span.update(
                    output={"result_count": result_count, "found": document is not None}
                )

                return document

    async def get_chunks_by_document(self, document_id: UUID) -> list[Chunk]:
        async with self.database_connection.get_session() as session:
            stmt = (
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            )
            query_sql = compile_query(stmt)

            with self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.repository.get_chunks_by_document",
                metadata=structlog.contextvars.get_contextvars(),
            ) as retriever_span:
                retriever_span.update(input={"query": query_sql})

                result = await session.execute(stmt)
                chunks = list(result.scalars().all())

                result_count = len(chunks)
                retriever_span.update(
                    output={"result_count": result_count, "found": result_count > 0}
                )

                return chunks

    async def get_embedding_version_by_id(
        self, version_id: UUID
    ) -> Optional[EmbeddingVersion]:
        async with self.database_connection.get_session() as session:
            stmt = select(EmbeddingVersion).where(EmbeddingVersion.id == version_id)
            query_sql = compile_query(stmt)

            with self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.repository.get_embedding_version_by_id",
                metadata=structlog.contextvars.get_contextvars(),
            ) as retriever_span:
                retriever_span.update(input={"query": query_sql})

                result = await session.execute(stmt)
                embedding_version = result.scalar_one_or_none()

                result_count = 1 if embedding_version else 0
                retriever_span.update(
                    output={
                        "result_count": result_count,
                        "found": embedding_version is not None,
                    }
                )

                return embedding_version

    async def get_query_cache_by_hash(self, query_hash: str) -> Optional[QueryCache]:
        async with self.database_connection.get_session() as session:
            stmt = select(QueryCache).where(QueryCache.query_hash == query_hash)
            query_sql = compile_query(stmt)

            with self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.repository.get_query_cache_by_hash",
                metadata=structlog.contextvars.get_contextvars(),
            ) as retriever_span:
                retriever_span.update(input={"query": query_sql})

                result = await session.execute(stmt)
                query_cache = result.scalar_one_or_none()

                result_count = 1 if query_cache else 0
                retriever_span.update(
                    output={
                        "result_count": result_count,
                        "found": query_cache is not None,
                    }
                )

                return query_cache

    async def save_query_cache(self, query_cache: QueryCache) -> QueryCache:
        async with self.database_connection.get_session() as session:
            session.add(query_cache)
            await session.flush()
            await session.refresh(query_cache)
            return query_cache

    async def update_query_cache_usage(self, cache_id: UUID) -> None:
        async with self.database_connection.get_session() as session:
            await session.execute(
                update(QueryCache)
                .where(QueryCache.id == cache_id)
                .values(
                    use_count=QueryCache.use_count + 1, last_used_at=datetime.utcnow()
                )
            )

    async def find_document_by_hash(
        self, tenant_id: str, content_hash: str
    ) -> Optional[Document]:
        async with self.database_connection.get_session() as session:
            stmt = select(Document).where(
                and_(
                    Document.tenant_id == tenant_id,
                    Document.content_hash == content_hash,
                )
            )
            query_sql = compile_query(stmt)

            with self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.repository.find_document_by_hash",
                metadata=structlog.contextvars.get_contextvars(),
            ) as retriever_span:
                retriever_span.update(input={"query": query_sql})

                result = await session.execute(stmt)
                document = result.scalar_one_or_none()

                result_count = 1 if document else 0
                retriever_span.update(
                    output={"result_count": result_count, "found": document is not None}
                )

                return document

    async def save_document(self, document: Document) -> None:
        async with self.database_connection.get_session() as session:
            session.add(document)
            await session.flush()
            await session.refresh(document)

    async def save_chunk(self, chunk: Chunk) -> None:
        async with self.database_connection.get_session() as session:
            session.add(chunk)
            await session.flush()
# services.py

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from langfuse import Langfuse

import structlog
from adapters.llm.llm_client import LLMClient
from services.rag.embedding_version_service import EmbeddingVersionService
from domain.rag.services.retrieval_service import SimilarChunk
from adapters.observability.logging import get_logger

logger = get_logger()


class GenerationService:
    def __init__(
        self,
        llm_client: LLMClient,
        embedding_version_service: EmbeddingVersionService,
        langfuse: "Langfuse" = None,
    ) -> None:
        self.llm_client = llm_client
        self.embedding_version_service = embedding_version_service
        self.langfuse = langfuse

    async def generate_response(
        self,
        query: str,
        retrieved_chunks: List[SimilarChunk],
        system_instruction: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> str:
        if not retrieved_chunks:
            return "Não tenho informações suficientes para responder."

        prompt = self._build_prompt(system_instruction, retrieved_chunks, query)

        response = await self.llm_client.generate(
            prompt=prompt, max_tokens=max_tokens, temperature=temperature
        )

        if self.langfuse:
            evaluator_context = self.langfuse.start_as_current_observation(
                as_type="evaluator",
                name="evaluator.rag_grounding_check",
                metadata=structlog.contextvars.get_contextvars(),
            )
            evaluator_span = evaluator_context.__enter__()
        else:
            evaluator_span = None
            evaluator_context = None

        try:
            is_grounded = self._validate_response(str(response), retrieved_chunks)

            if evaluator_span:
                evaluator_span.update(
                    input={
                        "response": str(response)[:200],
                        "chunks_count": len(retrieved_chunks),
                    },
                    output={"is_grounded": is_grounded},
                )

            if not is_grounded:
                logger.warning(
                    "Response may not be grounded in retrieved context",
                    query_preview=query[:100],
                    action="rag_response_validation_failed",
                )
                if evaluator_context:
                    evaluator_context.__exit__(None, None, None)
                return "Não tenho informações suficientes para responder."

            logger.info(
                "Response generated via RAG",
                query_preview=query[:100],
                chunks_used=len(retrieved_chunks),
                action="rag_response_generated",
            )

            if evaluator_context:
                evaluator_context.__exit__(None, None, None)

            return str(response)
        except Exception as e:
            if evaluator_span:
                evaluator_span.update(
                    input={"response": str(response)[:200]},
                    output={"is_grounded": False, "error": str(e)},
                )
            if evaluator_context:
                evaluator_context.__exit__(None, None, None)
            raise

    def _build_prompt(
        self, system_instruction: str, retrieved_chunks: List[SimilarChunk], query: str
    ) -> str:
        context_parts = []
        for chunk in retrieved_chunks:
            context_parts.append(f"- {chunk.chunk.content}")

        context_text = "\n".join(context_parts)

        prompt = f"""{system_instruction}

## Contexto Recuperado:
{context_text}

## Pergunta:
{query}

## Instrução:
Responda APENAS com base no contexto recuperado. Se não houver informação suficiente no contexto, responda: "Não tenho informações suficientes para responder."
"""
        return prompt

    def _validate_response(
        self, response: str, retrieved_chunks: List[SimilarChunk]
    ) -> bool:
        if not retrieved_chunks:
            return False

        response_lower = response.lower()
        fallback_indicators = [
            "não tenho informações",
            "não tenho informação",
            "não sei",
            "não posso responder",
        ]

        for indicator in fallback_indicators:
            if indicator in response_lower:
                return True

        context_text = " ".join(
            [chunk.chunk.content.lower() for chunk in retrieved_chunks]
        )

        words_in_response = set(response_lower.split())
        words_in_context = set(context_text.split())

        common_words = words_in_response.intersection(words_in_context)

        if len(common_words) < 3:
            return False

        return True

import asyncio
import hashlib
from typing import Optional
from datetime import datetime

from infra.database.models.rag.document import Document
from infra.database.models.rag.chunk import Chunk
from domain.rag.repositories.rag_repository import RAGRepository
from domain.rag.adapters.chunking_adapter import ChunkingAdapter, ChunkData
from services.rag.embedding_version_service import EmbeddingVersionService
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from adapters.observability.logging import get_logger

logger = get_logger()


class IngestionService:
    MAX_CONTENT_SIZE = 100000
    MAX_CHUNKS = 100

    def __init__(
        self,
        rag_repository: RAGRepository,
        embedding_adapter: OpenAIEmbeddingAdapter,
        chunking_adapter: ChunkingAdapter,
        embedding_version_service: EmbeddingVersionService,
    ) -> None:
        self.rag_repository = rag_repository
        self.embedding_adapter = embedding_adapter
        self.chunking_adapter = chunking_adapter
        self.embedding_version_service = embedding_version_service

    async def ingest_document(
        self,
        tenant_id: str,
        content: str,
        source: str,
        doc_type: str,
        version: str,
        metadata: dict,
    ) -> Document:
        embedding_version = await self.embedding_version_service.get_default_version()
        if not embedding_version:
            raise ValueError("No default embedding version found")

        if len(content) > self.MAX_CONTENT_SIZE:
            raise ValueError(f"Content exceeds maximum size: {self.MAX_CONTENT_SIZE}")

        content_hash = self._calculate_hash(content)

        existing_doc = await self.rag_repository.find_document_by_hash(
            tenant_id, content_hash
        )

        if existing_doc:
            logger.debug(
                "Document already exists, skipping ingestion",
                document_id=str(existing_doc.id),
                content_hash=content_hash,
            )
            return existing_doc

        document = Document(
            tenant_id=tenant_id,
            content=content,
            content_hash=content_hash,
            meta_data=metadata,
            source=source,
            type=doc_type,
            version=version,
        )

        await self.rag_repository.save_document(document)

        chunks_data = self.chunking_adapter.chunk_text(
            text=content, target_tokens=500, overlap_tokens=50
        )

        if len(chunks_data) > self.MAX_CHUNKS:
            logger.warning(
                "Chunks count exceeds maximum",
                chunks_count=len(chunks_data),
                max_chunks=self.MAX_CHUNKS,
            )
            chunks_data = chunks_data[: self.MAX_CHUNKS]

        semaphore = asyncio.Semaphore(3)

        async def process_chunk(idx: int, chunk_data: ChunkData) -> Optional[Chunk]:
            async with semaphore:
                try:
                    chunk_hash = self._calculate_hash(chunk_data.content)

                    embedding = await self.embedding_adapter.generate_embedding(
                        text=chunk_data.content,
                    )

                    chunk = Chunk(
                        document_id=document.id,
                        embedding_version_id=embedding_version.id,
                        chunk_index=idx,
                        content=chunk_data.content,
                        content_hash=chunk_hash,
                        token_count=chunk_data.token_count,
                        embedding=embedding,
                        meta_data=chunk_data.metadata,
                        embedding_generated_at=datetime.utcnow(),
                    )

                    await self.rag_repository.save_chunk(chunk)
                    return chunk
                except Exception as e:
                    logger.warning(
                        "Error processing chunk", chunk_index=idx, error=str(e)
                    )
                    return None

        tasks = [
            process_chunk(idx, chunk_data) for idx, chunk_data in enumerate(chunks_data)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_chunks = [
            r for r in results if r is not None and not isinstance(r, Exception)
        ]

        logger.info(
            "Document ingested successfully",
            document_id=str(document.id),
            tenant_id=tenant_id,
            source=source,
            chunks_count=len(chunks_data),
            successful_chunks=len(successful_chunks),
            action="rag_document_ingested",
        )

        return document

    def _calculate_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


import hashlib
from typing import List, Optional, TYPE_CHECKING, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import text

if TYPE_CHECKING:
    from langfuse import Langfuse

import structlog
from infra.database.models.rag.chunk import Chunk
from infra.database.models.rag.query_cache import QueryCache
from infra.database.models.rag.embedding_version import EmbeddingVersion
from services.rag.embedding_version_service import EmbeddingVersionService
from domain.rag.repositories.rag_repository import RAGRepository
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from adapters.llm.cost_calculator import calculate_embedding_cost
from adapters.observability.logging import get_logger

logger = get_logger()


class SimilarChunk:
    def __init__(self, chunk: Chunk, similarity: float, score: float) -> None:
        self.chunk = chunk
        self.similarity = similarity
        self.score = score


class RetrievalService:
    def __init__(
        self,
        rag_repository: RAGRepository,
        embedding_adapter: OpenAIEmbeddingAdapter,
        embedding_version_service: EmbeddingVersionService,
        langfuse: Optional["Langfuse"] = None,
        memory_store: Optional[Any] = None,
        embedding_cache_ttl: int = 3600,
    ) -> None:
        self.rag_repository = rag_repository
        self.embedding_adapter = embedding_adapter
        self.embedding_version_service = embedding_version_service
        self.langfuse = langfuse
        self.memory_store = memory_store
        self.embedding_cache_ttl = embedding_cache_ttl

    async def search_similar_chunks(
        self,
        tenant_id: str,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = 0.85,
        filters: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> List[SimilarChunk]:
        if self.langfuse:
            retriever_context = self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.retrieval_service.search_similar_chunks",
                metadata={
                    **structlog.contextvars.get_contextvars(),
                    "tenant_id": tenant_id,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
            )
            retriever_span = retriever_context.__enter__()
        else:
            retriever_span = None
            retriever_context = None

        try:
            embedding_version = (
                await self.embedding_version_service.get_default_version()
            )
            if not embedding_version:
                logger.warning("No default embedding version found")
                if retriever_context:
                    retriever_context.__exit__(None, None, None)
                return []

            query_embedding = await self._get_or_create_query_embedding_with_ttl_cache(
                query_text, embedding_version, tenant_id, user_id
            )

            if query_embedding is None:
                if retriever_context:
                    retriever_context.__exit__(None, None, None)
                return []

            async with self.rag_repository.database_connection.get_session() as session:
                query = self._build_similarity_query(
                    query_embedding, embedding_version.id, tenant_id, top_k, filters
                )

                result = await session.execute(text(query))
                rows = result.fetchall()

                similar_chunks = []
                for row in rows:
                    chunk_id = row[0]
                    similarity = float(row[1])

                    if similarity < similarity_threshold:
                        continue

                    chunk = await self.rag_repository.get_chunk_by_id(chunk_id)
                    if chunk:
                        similar_chunks.append(
                            SimilarChunk(
                                chunk=chunk, similarity=similarity, score=similarity
                            )
                        )

                if retriever_span:
                    retriever_span.update(
                        input={"query_text": query_text, "filters": filters},
                        output={
                            "chunks_found": len(similar_chunks),
                            "max_similarity": similar_chunks[0].similarity
                            if similar_chunks
                            else 0.0,
                        },
                        usage_details={
                            "query_tokens": len(query_text.split()),
                        },
                    )

                query_hash = self._calculate_hash(query_text)
                logger.info(
                    "Similarity search completed",
                    tenant_id=tenant_id,
                    query_hash=query_hash,
                    top_k=top_k,
                    results_count=len(similar_chunks),
                    max_similarity=similar_chunks[0].similarity
                    if similar_chunks
                    else 0.0,
                    action="rag_similarity_search",
                )

                if retriever_context:
                    retriever_context.__exit__(None, None, None)

                return similar_chunks
        except Exception as e:
            if retriever_span:
                retriever_span.update(
                    input={"query_text": query_text, "filters": filters},
                    output={"error": str(e)},
                )
            if retriever_context:
                retriever_context.__exit__(None, None, None)
            raise

    async def search_similar_chunks_with_embedding(
        self,
        tenant_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        similarity_threshold: float = 0.85,
        filters: Optional[dict] = None,
    ) -> List[SimilarChunk]:
        if self.langfuse:
            retriever_context = self.langfuse.start_as_current_observation(
                as_type="retriever",
                name="domain.rag.retrieval_service.search_similar_chunks_with_embedding",
                metadata={
                    **structlog.contextvars.get_contextvars(),
                    "tenant_id": tenant_id,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
            )
            retriever_span = retriever_context.__enter__()
        else:
            retriever_span = None
            retriever_context = None

        try:
            embedding_version = (
                await self.embedding_version_service.get_default_version()
            )
            if not embedding_version:
                logger.warning("No default embedding version found")
                if retriever_context:
                    retriever_context.__exit__(None, None, None)
                return []

            async with self.rag_repository.database_connection.get_session() as session:
                query = self._build_similarity_query(
                    query_embedding, embedding_version.id, tenant_id, top_k, filters
                )

                result = await session.execute(text(query))
                rows = result.fetchall()

                similar_chunks = []
                for row in rows:
                    chunk_id = row[0]
                    similarity = float(row[1])

                    if similarity < similarity_threshold:
                        continue

                    chunk = await self.rag_repository.get_chunk_by_id(chunk_id)
                    if chunk:
                        similar_chunks.append(
                            SimilarChunk(
                                chunk=chunk, similarity=similarity, score=similarity
                            )
                        )

                if retriever_span:
                    retriever_span.update(
                        input={
                            "filters": filters,
                            "embedding_length": len(query_embedding),
                        },
                        output={
                            "chunks_found": len(similar_chunks),
                            "max_similarity": similar_chunks[0].similarity
                            if similar_chunks
                            else 0.0,
                        },
                    )

                logger.info(
                    "Similarity search completed with cached embedding",
                    tenant_id=tenant_id,
                    top_k=top_k,
                    results_count=len(similar_chunks),
                    max_similarity=similar_chunks[0].similarity
                    if similar_chunks
                    else 0.0,
                    action="rag_similarity_search_cached",
                )

                if retriever_context:
                    retriever_context.__exit__(None, None, None)

                return similar_chunks
        except Exception as e:
            if retriever_span:
                retriever_span.update(
                    input={"filters": filters},
                    output={"error": str(e)},
                )
            if retriever_context:
                retriever_context.__exit__(None, None, None)
            raise

    async def _get_or_create_query_embedding_with_ttl_cache(
        self,
        query_text: str,
        embedding_version: EmbeddingVersion,
        tenant_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[List[float]]:
        query_hash = self._calculate_hash(query_text)
        cache_key = f"rag:embed:{embedding_version.id}:{query_hash}"

        if self.memory_store and user_id:
            cached_embedding = await self.memory_store.retrieve(
                tenant_id, user_id, cache_key
            )
            if cached_embedding and cached_embedding.get("embedding"):
                logger.info(
                    "Embedding TTL cache hit",
                    query_hash=query_hash,
                    embedding_version_id=str(embedding_version.id),
                    action="rag_embedding_ttl_cache_hit",
                )
                return cached_embedding["embedding"]

        query_embedding = await self._get_or_create_query_embedding(
            query_text, embedding_version
        )

        if query_embedding is not None and self.memory_store and user_id:
            await self.memory_store.store(
                tenant_id,
                user_id,
                cache_key,
                {"embedding": query_embedding, "query_hash": query_hash},
                ttl=self.embedding_cache_ttl,
            )
            logger.debug(
                "Embedding stored in TTL cache",
                query_hash=query_hash,
                ttl=self.embedding_cache_ttl,
                action="rag_embedding_ttl_cache_stored",
            )

        return query_embedding

    async def _get_or_create_query_embedding(
        self, query_text: str, embedding_version: EmbeddingVersion
    ) -> Optional[List[float]]:
        query_hash = self._calculate_hash(query_text)

        cached = await self.rag_repository.get_query_cache_by_hash(query_hash)
        if cached and cached.embedding is not None:
            estimated_tokens = len(query_text.split()) * 1.3
            estimated_cost = calculate_embedding_cost(
                model=embedding_version.model_name, input_tokens=int(estimated_tokens)
            )
            logger.info(
                "Query cache hit",
                query_hash=query_hash,
                use_count=cached.use_count + 1,
                cost_saved_usd=estimated_cost,
                action="rag_query_cache_hit",
            )
            await self.rag_repository.update_query_cache_usage(cached.id)
            return cached.embedding

        embedding = await self.embedding_adapter.generate_embedding(text=query_text)

        query_cache = QueryCache(
            query_hash=query_hash,
            query_text=query_text,
            embedding_version_id=embedding_version.id,
            embedding=embedding,
            last_used_at=datetime.utcnow(),
            use_count=1,
        )
        await self.rag_repository.save_query_cache(query_cache)

        logger.info(
            "Query embedding generated and cached",
            query_hash=query_hash,
            action="rag_query_embedding_generated",
        )

        return embedding

    def _calculate_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _build_similarity_query(
        self,
        query_embedding: List[float],
        embedding_version_id: UUID,
        tenant_id: str,
        top_k: int,
        filters: Optional[dict],
    ) -> str:
        embedding_array = "[" + ",".join(map(str, query_embedding)) + "]"

        base_query = f"""
            SELECT
                chunk.id,
                1 - (chunk.embedding <=> '{embedding_array}'::vector) as similarity
            FROM rag_chunks chunk
            JOIN rag_documents doc ON chunk.document_id = doc.id
            WHERE chunk.embedding_version_id = '{embedding_version_id}'
            AND doc.tenant_id = '{tenant_id}'
            AND chunk.embedding IS NOT NULL
        """

        if filters:
            if filters.get("type"):
                base_query += f" AND doc.type = '{filters['type']}'"
            if filters.get("source"):
                base_query += f" AND doc.source = '{filters['source']}'"

        base_query += f"""
            ORDER BY chunk.embedding <=> '{embedding_array}'::vector
            LIMIT {top_k}
        """

        return base_query


# embeeding_adatper.py

from typing import List
from openai import AsyncOpenAI
from langfuse import Langfuse
import structlog
from settings import (
    RAG_EMBEDDING_MODEL,
    RAG_EMBEDDING_DIMENSION,
)
from adapters.llm.cost_calculator import (
    calculate_embedding_cost,
    accumulate_rag_cost_in_context,
)
from adapters.observability.logging import get_logger

logger = get_logger()


class OpenAIEmbeddingAdapter:
    def __init__(
        self,
        api_key: str,
        langfuse: Langfuse,
        model: str = RAG_EMBEDDING_MODEL,
        dimension: int = RAG_EMBEDDING_DIMENSION,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = dimension
        self.langfuse = langfuse

    async def generate_embedding(self, text: str) -> List[float]:
        with self.langfuse.start_as_current_observation(
            as_type="embedding",
            name="adapters.llm.openai_embedding_adapter.generate_embedding",
            model=self.model,
            metadata=structlog.contextvars.get_contextvars(),
        ) as generation:
            result = await self._call_embedding_api(text)
            generation.update(
                input=text,
                output={"dimension": len(result)},
                model_parameters={
                    "model": self.model,
                    "dimension": self.dimension,
                },
            )
            return result

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        with self.langfuse.start_as_current_observation(
            as_type="embedding",
            name="adapters.llm.openai_embedding_adapter.generate_embeddings_batch",
            model=self.model,
            metadata=structlog.contextvars.get_contextvars(),
        ) as generation:
            result = await self._call_embedding_batch_api(texts)
            generation.update(
                input=texts,
                output={
                    "count": len(result),
                    "dimension": len(result[0]) if result else 0,
                },
                model_parameters={
                    "model": self.model,
                    "dimension": self.dimension,
                },
            )
            return result

    async def _call_embedding_api(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dimension
        )

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        cost = calculate_embedding_cost(model=self.model, input_tokens=input_tokens)
        accumulate_rag_cost_in_context(cost)

        logger.info(
            "Embedding generated",
            model=self.model,
            input_tokens=input_tokens,
            embedding_cost_usd=cost,
            action="rag_embedding_generated",
        )

        return response.data[0].embedding

    async def _call_embedding_batch_api(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dimension
        )

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        cost = calculate_embedding_cost(model=self.model, input_tokens=input_tokens)
        accumulate_rag_cost_in_context(cost)

        logger.info(
            "Embeddings batch generated",
            model=self.model,
            batch_size=len(texts),
            input_tokens=input_tokens,
            embedding_cost_usd=cost,
            cost_per_embedding=cost / len(texts) if texts else 0.0,
        )
        return [item.embedding for item in response.data]