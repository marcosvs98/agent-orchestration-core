from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.rag.schemas.rag import (
    DEFAULT_EMBEDDING_DIMENSION,
    EMBEDDING_DIMENSION_REDUCED,
)
from infra.database import DatabaseConnection
from infra.database.models.llm.semantic_answer_cache import (
    SemanticAnswerCache as SemanticAnswerCacheModel,
)


class SemanticCacheRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    ) -> None:
        self.db = database_connection
        self.embedding_dimension = embedding_dimension

    async def search_similar(
        self,
        *,
        tenant_id: UUID,
        task_type: str,
        query_embedding: list[float],
        similarity_threshold: float,
        now: datetime,
    ) -> SemanticAnswerCacheModel | None:
        if self.embedding_dimension == EMBEDDING_DIMENSION_REDUCED:
            distance_expr = SemanticAnswerCacheModel.embedding_512.cosine_distance(
                query_embedding
            )
        else:
            distance_expr = SemanticAnswerCacheModel.embedding.cosine_distance(
                query_embedding
            )
        stmt = (
            select(
                SemanticAnswerCacheModel,
                distance_expr.label("distance"),
            )
            .where(SemanticAnswerCacheModel.tenant_id == tenant_id)
            .where(SemanticAnswerCacheModel.task_type == task_type)
            .where(SemanticAnswerCacheModel.expires_at > now)
            .where(distance_expr <= (1.0 - similarity_threshold))
        )
        if self.embedding_dimension == EMBEDDING_DIMENSION_REDUCED:
            stmt = stmt.where(SemanticAnswerCacheModel.embedding_512.is_not(None))
        else:
            stmt = stmt.where(SemanticAnswerCacheModel.embedding.is_not(None))
        stmt = stmt.order_by(distance_expr.asc()).limit(1)
        async with self.db.get_session() as session:
            result = await session.execute(stmt)
            row = result.first()
            if row is None:
                return None
            cache_entry = row[0]
            distance = float(row[1])
            cache_entry.similarity_score = 1.0 - distance
            return cache_entry

    async def persist(self, *, entry: SemanticAnswerCacheModel) -> None:
        values = {
            "cache_id": entry.cache_id,
            "tenant_id": entry.tenant_id,
            "task_type": entry.task_type,
            "query_hash": entry.query_hash,
            "embedding": entry.embedding,
            "embedding_512": getattr(entry, "embedding_512", None),
            "response_json": entry.response_json,
            "model_alias": entry.model_alias,
            "inference_layer": entry.inference_layer,
            "similarity_score": entry.similarity_score,
            "ttl_seconds": entry.ttl_seconds,
            "hit_count": entry.hit_count,
            "expires_at": entry.expires_at,
            "last_hit_at": entry.last_hit_at,
            "created_at": entry.created_at,
        }
        stmt = (
            pg_insert(SemanticAnswerCacheModel)
            .values(values)
            .on_conflict_do_update(
                constraint="uq_semantic_answer_cache_tenant_task_query",
                set_={
                    "embedding": entry.embedding,
                    "embedding_512": getattr(entry, "embedding_512", None),
                    "response_json": entry.response_json,
                    "model_alias": entry.model_alias,
                    "inference_layer": entry.inference_layer,
                    "similarity_score": entry.similarity_score,
                    "ttl_seconds": entry.ttl_seconds,
                    "expires_at": entry.expires_at,
                    "last_hit_at": entry.last_hit_at,
                },
            )
        )
        async with self.db.get_session() as session:
            await session.execute(stmt)
            await session.commit()

    async def increment_hit(self, *, cache_id: UUID, now: datetime) -> None:
        stmt = (
            update(SemanticAnswerCacheModel)
            .where(SemanticAnswerCacheModel.cache_id == cache_id)
            .values(
                hit_count=SemanticAnswerCacheModel.hit_count + 1,
                last_hit_at=now,
            )
        )
        async with self.db.get_session() as session:
            await session.execute(stmt)
            await session.commit()

    async def evict_expired(self, *, tenant_id: UUID, now: datetime) -> int:
        stmt = delete(SemanticAnswerCacheModel).where(
            SemanticAnswerCacheModel.tenant_id == tenant_id,
            SemanticAnswerCacheModel.expires_at <= now,
        )
        async with self.db.get_session() as session:
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount or 0)
