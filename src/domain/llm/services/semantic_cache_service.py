from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4, UUID

from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.llm.repositories.semantic_cache_repository import SemanticCacheRepository
from domain.llm.schemas.inference_cache import CacheLookupResult, SemanticCacheEntry
from infra.database.models.llm.semantic_answer_cache import (
    SemanticAnswerCache as SemanticAnswerCacheModel,
)


class SemanticCacheService:
    def __init__(
        self,
        *,
        repository: SemanticCacheRepository,
        embedding_adapter: OpenAIEmbeddingAdapter,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.repository = repository
        self.embedding_adapter = embedding_adapter
        self.tracer = tracer

    async def lookup(
        self,
        *,
        tenant_id: UUID,
        task_type: str,
        user_query: str,
        similarity_threshold: float,
    ) -> CacheLookupResult:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.llm.semantic_cache.lookup",
            input={
                "tenant_id": str(tenant_id),
                "task_type": task_type,
                "similarity_threshold": similarity_threshold,
            },
        ) as retriever_handle:
            query_embedding = await self.embedding_adapter.generate_embedding(
                user_query
            )
            now = datetime.now(UTC)
            cache_entry = await self.repository.search_similar(
                tenant_id=tenant_id,
                task_type=task_type,
                query_embedding=query_embedding,
                similarity_threshold=similarity_threshold,
                now=now,
            )
            if cache_entry is None:
                result = CacheLookupResult(hit=False, query_embedding=query_embedding)
                if retriever_handle:
                    retriever_handle.success(output={"hit": False})
                return result
            similarity_score = cache_entry.similarity_score

            await self.repository.increment_hit(cache_id=cache_entry.cache_id, now=now)
            created_at = cache_entry.created_at
            if created_at is None:
                created_at = now
            if similarity_score is None:
                similarity_score = 0.0
            result = CacheLookupResult(
                hit=True,
                query_embedding=query_embedding,
                entry=SemanticCacheEntry(
                    cache_id=cache_entry.cache_id,
                    task_type=cache_entry.task_type,
                    response=cache_entry.response_json,
                    similarity_score=float(similarity_score),
                    model_alias=cache_entry.model_alias,
                    inference_layer=cache_entry.inference_layer,
                    created_at=created_at,
                ),
            )
            if retriever_handle:
                retriever_handle.success(
                    output={"hit": True, "similarity_score": similarity_score}
                )
            return result

    async def persist(
        self,
        *,
        tenant_id: UUID,
        task_type: str,
        user_query: str,
        query_embedding: list[float] | None,
        response: dict,
        model_alias: str | None,
        inference_layer: str,
        ttl_seconds: int,
        similarity_score: float | None = None,
    ) -> None:
        with self.tracer.observe(
            as_type="chain",
            name="domain.llm.semantic_cache.persist",
            input={
                "tenant_id": str(tenant_id),
                "task_type": task_type,
                "inference_layer": inference_layer,
                "ttl_seconds": ttl_seconds,
            },
        ) as chain_handle:
            effective_embedding = query_embedding
            if effective_embedding is None:
                effective_embedding = await self.embedding_adapter.generate_embedding(
                    user_query
                )
            now = datetime.now(UTC)
            expires_at = now + timedelta(seconds=ttl_seconds)
            entry = SemanticAnswerCacheModel(
                cache_id=uuid4(),
                tenant_id=tenant_id,
                task_type=task_type,
                query_hash=self._hash_text(user_query),
                embedding=effective_embedding,
                response_json=response,
                model_alias=model_alias,
                inference_layer=inference_layer,
                similarity_score=similarity_score,
                ttl_seconds=ttl_seconds,
                hit_count=0,
                expires_at=expires_at,
                last_hit_at=None,
                created_at=now,
            )
            await self.repository.persist(entry=entry)
            if chain_handle:
                chain_handle.success(output={"persisted": True})

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
