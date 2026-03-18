from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from adapters.cache.redis_adapter import RedisAdapter
from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.schemas.embedding_job import EmbeddingStatus
from domain.rag.schemas.rag import EMBEDDING_DIMENSION_REDUCED
from domain.rag.schemas.rag_tenant_summary import (
    RagConfigPreviewRow,
    RagTenantSummaryData,
)
from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.rag.rag_config import RagConfig as RagConfigModel
from infra.database.models.rag.rag_document import RagDocument as RagDocumentModel
from infra.database.models.rag.rag_chunk import RagChunk as RagChunkModel
from infra.database.models.rag.rag_query_cache import (
    RagQueryCache as RagQueryCacheModel,
)
from infra.database.models.rag.vector_store import VectorStore as VectorStoreModel
from utils.query_compiler import compile_query


class RagRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort | None = None,
        cache_adapter: RedisAdapter | None = None,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer
        self.cache_adapter = cache_adapter

    async def get_vector_store(
        self, vector_store_id: UUID, *, tenant_id: UUID | None = None
    ) -> VectorStoreModel | None:
        async with self.db.get_session() as session:
            stmt = select(VectorStoreModel).where(
                VectorStoreModel.vector_store_id == vector_store_id
            )
            if tenant_id is not None:
                stmt = stmt.where(VectorStoreModel.tenant_id == tenant_id)
            query_sql = compile_query(stmt)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.get_vector_store",
                    input={
                        "query": query_sql,
                        "params": {
                            "vector_store_id": str(vector_store_id),
                            "tenant_id": str(tenant_id) if tenant_id else None,
                        },
                    },
                    metadata={"retriever_name": "get_vector_store"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if row else 0,
                                "found": row is not None,
                            }
                        )
                    return row
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_vector_stores(self, *, tenant_id: UUID) -> list[VectorStoreModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(VectorStoreModel)
                .where(VectorStoreModel.tenant_id == tenant_id)
                .order_by(
                    VectorStoreModel.name.asc().nulls_last(),
                    VectorStoreModel.vector_store_id.asc(),
                )
            )
            query_sql = compile_query(stmt)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.list_vector_stores",
                    input={
                        "query": query_sql,
                        "params": {"tenant_id": str(tenant_id)},
                    },
                    metadata={"retriever_name": "list_vector_stores"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    rows = list(result.scalars().all())
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": len(rows),
                                "found": len(rows) > 0,
                            }
                        )
                    return rows
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_vector_store(
        self, *, tenant_id: UUID, name: str
    ) -> VectorStoreModel:
        async with self.db.get_session() as session:
            instance = VectorStoreModel(tenant_id=tenant_id, name=name)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_rag_config(self, rag_config_id: UUID) -> RagConfigModel | None:
        key = f"rag_config:{rag_config_id}"
        if self.cache_adapter:
            cached = await self.cache_adapter.get(key)
            if cached:
                return RagConfigModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(RagConfigModel).where(
                RagConfigModel.rag_config_id == rag_config_id
            )
            query_sql = compile_query(stmt)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.get_rag_config",
                    input={
                        "query": query_sql,
                        "params": {"rag_config_id": str(rag_config_id)},
                    },
                    metadata={"retriever_name": "get_rag_config"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if row else 0,
                                "found": row is not None,
                            }
                        )
                    if self.cache_adapter and row:
                        await self.cache_adapter.set(key, row.to_dict(), ttl=60)
                    return row
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if self.cache_adapter and row:
                await self.cache_adapter.set(key, row.to_dict(), ttl=60)
            return row

    async def get_published_rag_config_id_for_vector_store(
        self, *, tenant_id: UUID, vector_store_id: UUID
    ) -> UUID | None:
        async with self.db.get_session() as session:
            stmt = (
                select(RagConfigModel.rag_config_id)
                .where(
                    RagConfigModel.tenant_id == tenant_id,
                    RagConfigModel.vector_store_id == vector_store_id,
                    RagConfigModel.status == VersionStatus.PUBLISHED.value,
                )
                .order_by(
                    RagConfigModel.version_major.desc(),
                    RagConfigModel.version_minor.desc(),
                    RagConfigModel.version_patch.desc(),
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_rag_configs(
        self,
        *,
        tenant_id: UUID,
        status_filter: list[str] | None = None,
        limit: int,
    ) -> list[RagConfigModel]:
        async with self.db.get_session() as session:
            stmt = select(RagConfigModel).where(RagConfigModel.tenant_id == tenant_id)
            if status_filter is not None:
                stmt = stmt.where(RagConfigModel.status.in_(status_filter))
            stmt = stmt.order_by(
                RagConfigModel.version_major.desc(),
                RagConfigModel.version_minor.desc(),
                RagConfigModel.version_patch.desc(),
            ).limit(limit)
            query_sql = compile_query(stmt)
            params: dict[str, object] = {
                "tenant_id": str(tenant_id),
                "limit": limit,
            }
            if status_filter is not None:
                params["status_filter"] = status_filter
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.list_rag_configs",
                    input={"query": query_sql, "params": params},
                    metadata={"retriever_name": "list_rag_configs"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    rows = list(result.scalars().all())
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": len(rows),
                                "found": len(rows) > 0,
                            }
                        )
                    return rows
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_rag_config(
        self,
        *,
        tenant_id: UUID,
        source_version_id: UUID | None = None,
        vector_store_id: UUID,
        options: dict[str, object] | None = None,
        version_major: int | None = None,
        version_minor: int | None = None,
        version_patch: int | None = None,
        config_hash: str | None = None,
        created_by: str,
    ) -> RagConfigModel:
        async with self.db.get_session() as session:
            if source_version_id is not None:
                source_version = await session.execute(
                    select(RagConfigModel).where(
                        RagConfigModel.rag_config_id == source_version_id
                    )
                )
                source = source_version.scalar_one_or_none()
                if source is None:
                    raise NotFoundServiceException(message="source_version_not_found")
                if source.tenant_id != tenant_id:
                    raise NotFoundServiceException(message="source_version_not_found")
                if version_major is None:
                    version_major = source.version_major
                if version_minor is None:
                    version_minor = source.version_minor
                if version_patch is None:
                    version_patch = source.version_patch + 1
                if config_hash is None:
                    config_hash = source.config_hash
                if options is None:
                    options = source.options
            else:
                if (
                    version_major is None
                    or version_minor is None
                    or version_patch is None
                ):
                    last_version = await session.execute(
                        select(RagConfigModel)
                        .where(RagConfigModel.tenant_id == tenant_id)
                        .order_by(
                            RagConfigModel.version_major.desc(),
                            RagConfigModel.version_minor.desc(),
                            RagConfigModel.version_patch.desc(),
                        )
                        .limit(1)
                    )
                    last = last_version.scalar_one_or_none()
                    if last is None:
                        version_major = 1
                        version_minor = 0
                        version_patch = 0
                    else:
                        if version_major is None:
                            version_major = last.version_major
                        if version_minor is None:
                            version_minor = last.version_minor
                        if version_patch is None:
                            version_patch = last.version_patch + 1

            instance = RagConfigModel(
                tenant_id=tenant_id,
                vector_store_id=vector_store_id,
                status=VersionStatus.DRAFT,
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                config_hash=config_hash,
                options=options,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def set_rag_config_status(
        self, *, rag_config_id: UUID, status: VersionStatus
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RagConfigModel).where(
                    RagConfigModel.rag_config_id == rag_config_id
                )
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="rag_config_not_found")
            instance.status = str(status)
            await session.commit()

    async def get_document_by_hash(
        self, *, tenant_id: UUID, content_hash: str
    ) -> RagDocumentModel | None:
        async with self.db.get_session() as session:
            stmt = select(RagDocumentModel).where(
                RagDocumentModel.tenant_id == tenant_id,
                RagDocumentModel.content_hash == content_hash,
            )
            query_sql = compile_query(stmt)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.get_document_by_hash",
                    input={
                        "query": query_sql,
                        "params": {
                            "tenant_id": str(tenant_id),
                            "content_hash": content_hash,
                        },
                    },
                    metadata={"retriever_name": "get_document_by_hash"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if row else 0,
                                "found": row is not None,
                            }
                        )
                    return row
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_document(
        self,
        *,
        tenant_id: UUID,
        source: str | None,
        doc_type: str | None,
        content_hash: str,
        content: str | None,
        version: str | None,
        metadata: dict[str, object] | None,
        embedding_status: EmbeddingStatus = EmbeddingStatus.PENDING,
        rag_config_id: UUID | None = None,
    ) -> RagDocumentModel:
        async with self.db.get_session() as session:
            instance = RagDocumentModel(
                tenant_id=tenant_id,
                source=source,
                doc_type=doc_type,
                content_hash=content_hash,
                content=content,
                version=version,
                embedding_status=embedding_status.value,
                doc_metadata=metadata,
                rag_config_id=rag_config_id,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_document_by_id(self, *, document_id: UUID) -> RagDocumentModel | None:
        async with self.db.get_session() as session:
            stmt = select(RagDocumentModel).where(
                RagDocumentModel.document_id == document_id,
            )
            query_sql = compile_query(stmt)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.get_document_by_id",
                    input={
                        "query": query_sql,
                        "params": {"document_id": str(document_id)},
                    },
                    metadata={"retriever_name": "get_document_by_id"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if row else 0,
                                "found": row is not None,
                            }
                        )
                    return row
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_document_embedding_status(
        self,
        *,
        document_id: UUID,
        status: EmbeddingStatus,
        error_code: str | None = None,
        increment_attempts: bool = False,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> bool:
        async with self.db.get_session() as session:
            values: dict[str, object] = {
                "embedding_status": status.value,
                "updated_at": sa.func.now(),
                "last_embedding_error_code": error_code,
            }
            if increment_attempts:
                values["embedding_attempts"] = RagDocumentModel.embedding_attempts + 1
            if started_at is not None:
                values["embedding_started_at"] = started_at
            if completed_at is not None:
                values["embedding_completed_at"] = completed_at
            stmt = (
                update(RagDocumentModel)
                .where(RagDocumentModel.document_id == document_id)
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount or 0) > 0

    async def list_documents(
        self,
        *,
        tenant_id: UUID,
        limit: int,
        rag_config_id: UUID | None = None,
    ) -> list[RagDocumentModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(RagDocumentModel)
                .where(RagDocumentModel.tenant_id == tenant_id)
                .order_by(RagDocumentModel.created_at.desc())
                .limit(limit)
            )
            if rag_config_id is not None:
                stmt = stmt.where(RagDocumentModel.rag_config_id == rag_config_id)
            query_sql = compile_query(stmt)
            params: dict[str, object] = {"tenant_id": str(tenant_id), "limit": limit}
            if rag_config_id is not None:
                params["rag_config_id"] = str(rag_config_id)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.list_documents",
                    input={"query": query_sql, "params": params},
                    metadata={"retriever_name": "list_documents"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    rows = list(result.scalars().all())
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": len(rows),
                                "found": len(rows) > 0,
                            }
                        )
                    return rows
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count_documents_for_user(self, *, tenant_id: UUID, user_id: str) -> int:
        async with self.db.get_session() as session:
            stmt = (
                select(sa.func.count(RagDocumentModel.document_id))
                .where(RagDocumentModel.tenant_id == tenant_id)
                .where(RagDocumentModel.doc_metadata["scope"].astext == "USER_MEMORY")
                .where(RagDocumentModel.doc_metadata["user_id"].astext == user_id)
            )
            result = await session.execute(stmt)
            value = result.scalar()
            return int(value) if value is not None else 0

    async def list_chunks(
        self, *, document_id: UUID, limit: int
    ) -> list[RagChunkModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(RagChunkModel)
                .where(RagChunkModel.document_id == document_id)
                .order_by(RagChunkModel.chunk_index.asc())
                .limit(limit)
            )
            query_sql = compile_query(stmt)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.list_chunks",
                    input={
                        "query": query_sql,
                        "params": {"document_id": str(document_id), "limit": limit},
                    },
                    metadata={"retriever_name": "list_chunks"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    rows = list(result.scalars().all())
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": len(rows),
                                "found": len(rows) > 0,
                            }
                        )
                    return rows
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_chunks_pending_embedding_512(
        self, *, limit: int, offset: int = 0
    ) -> list[RagChunkModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(RagChunkModel)
                .where(RagChunkModel.embedding_512.is_(None))
                .where(RagChunkModel.embedding.is_not(None))
                .order_by(RagChunkModel.chunk_id.asc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_chunk_embedding_512(
        self, *, chunk_id: UUID, embedding_512: list[float]
    ) -> bool:
        async with self.db.get_session() as session:
            stmt = (
                update(RagChunkModel)
                .where(RagChunkModel.chunk_id == chunk_id)
                .values(embedding_512=embedding_512)
                .execution_options(synchronize_session=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount or 0) > 0

    async def create_chunks(self, *, chunks: list[RagChunkModel]) -> None:
        if not chunks:
            return
        async with self.db.get_session() as session:
            values: list[dict[str, object]] = []
            for chunk in chunks:
                values.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "content_hash": chunk.content_hash,
                        "token_count": chunk.token_count,
                        "embedding": chunk.embedding,
                        "embedding_512": getattr(chunk, "embedding_512", None),
                        "embedding_model": chunk.embedding_model,
                        "embedding_dimension": chunk.embedding_dimension,
                        "chunk_metadata": chunk.chunk_metadata,
                    }
                )
            stmt = (
                pg_insert(RagChunkModel)
                .values(values)
                .on_conflict_do_nothing(
                    index_elements=["document_id", "chunk_index"],
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def get_query_cache(
        self, *, tenant_id: UUID, query_hash: str
    ) -> RagQueryCacheModel | None:
        async with self.db.get_session() as session:
            stmt = select(RagQueryCacheModel).where(
                RagQueryCacheModel.tenant_id == tenant_id,
                RagQueryCacheModel.query_hash == query_hash,
            )
            query_sql = compile_query(stmt)
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.get_query_cache",
                    input={
                        "query": query_sql,
                        "params": {
                            "tenant_id": str(tenant_id),
                            "query_hash": query_hash,
                        },
                    },
                    metadata={"retriever_name": "get_query_cache"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if row else 0,
                                "found": row is not None,
                            }
                        )
                    return row
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_query_cache(
        self, *, cache_entry: RagQueryCacheModel
    ) -> RagQueryCacheModel:
        async with self.db.get_session() as session:
            session.add(cache_entry)
            await session.commit()
            await session.refresh(cache_entry)
            return cache_entry

    async def update_query_cache_usage(self, *, cache_id: UUID) -> None:
        async with self.db.get_session() as session:
            await session.execute(
                update(RagQueryCacheModel)
                .where(RagQueryCacheModel.query_cache_id == cache_id)
                .values(
                    use_count=RagQueryCacheModel.use_count + 1,
                    last_used_at=sa.func.now(),
                )
            )
            await session.commit()

    async def search_similar_chunks(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None,
        query_embedding: list[float],
        embedding_dimension: int,
        top_k: int,
        similarity_threshold: float,
        filters: dict[str, object] | None,
    ) -> list[tuple[RagChunkModel, float, datetime | None, str | None]]:
        if embedding_dimension == EMBEDDING_DIMENSION_REDUCED:
            distance_col = RagChunkModel.embedding_512.cosine_distance(query_embedding)
        else:
            distance_col = RagChunkModel.embedding.cosine_distance(query_embedding)
        async with self.db.get_session() as session:
            stmt = (
                select(
                    RagChunkModel,
                    distance_col.label("distance"),
                    RagDocumentModel.created_at.label("document_created_at"),
                    RagDocumentModel.doc_metadata["observed_at"].astext.label(
                        "document_observed_at"
                    ),
                )
                .join(
                    RagDocumentModel,
                    RagChunkModel.document_id == RagDocumentModel.document_id,
                )
                .where(RagDocumentModel.tenant_id == tenant_id)
            )
            if embedding_dimension == EMBEDDING_DIMENSION_REDUCED:
                stmt = stmt.where(RagChunkModel.embedding_512.is_not(None))
            else:
                stmt = stmt.where(RagChunkModel.embedding.is_not(None))
            if filters:
                if filters.get("source"):
                    stmt = stmt.where(RagDocumentModel.source == filters["source"])
                if filters.get("doc_type"):
                    stmt = stmt.where(RagDocumentModel.doc_type == filters["doc_type"])
                if filters.get("scope"):
                    scope_value = str(filters["scope"])
                    if scope_value == "TENANT_KNOWLEDGE":
                        stmt = stmt.where(
                            sa.or_(
                                RagDocumentModel.doc_metadata["scope"].astext
                                == scope_value,
                                RagDocumentModel.doc_metadata["scope"].astext.is_(None),
                            )
                        )
                    else:
                        stmt = stmt.where(
                            RagDocumentModel.doc_metadata["scope"].astext == scope_value
                        )
                if filters.get("user_id"):
                    stmt = stmt.where(
                        RagDocumentModel.doc_metadata["user_id"].astext
                        == str(filters["user_id"])
                    )
                if filters.get("category"):
                    stmt = stmt.where(
                        RagDocumentModel.doc_metadata["category"].astext
                        == str(filters["category"])
                    )
                if filters.get("tool_intent"):
                    stmt = stmt.where(
                        RagDocumentModel.doc_metadata["tool_intent"].astext
                        == str(filters["tool_intent"])
                    )
                if filters.get("created_after"):
                    created_after_value = filters["created_after"]
                    if isinstance(created_after_value, str):
                        created_after = datetime.fromisoformat(created_after_value)
                        stmt = stmt.where(RagDocumentModel.created_at >= created_after)
                if filters.get("expires_after"):
                    expires_after_value = filters["expires_after"]
                    if isinstance(expires_after_value, str):
                        stmt = stmt.where(
                            RagDocumentModel.doc_metadata["expires_at"].astext.is_not(
                                None
                            )
                        )
                        stmt = stmt.where(
                            RagDocumentModel.doc_metadata["expires_at"].astext
                            > expires_after_value
                        )
            if user_id:
                stmt = stmt.where(
                    RagDocumentModel.doc_metadata["user_id"].astext == user_id
                )
            stmt = stmt.order_by(sa.text("distance asc")).limit(top_k)
            query_sql = compile_query(stmt)
            params: dict[str, object] = {
                "tenant_id": str(tenant_id),
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
            }
            if user_id is not None:
                params["user_id"] = user_id
            if filters:
                params["filter_keys"] = list(filters.keys())
            if self.tracer:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.rag.rag_repository.search_similar_chunks",
                    input={"query": query_sql, "params": params},
                    metadata={"retriever_name": "search_similar_chunks"},
                ) as retriever_handle:
                    result = await session.execute(stmt)
                    rows = result.all()
                    items: list[
                        tuple[RagChunkModel, float, datetime | None, str | None]
                    ] = []
                    for (
                        chunk,
                        distance,
                        document_created_at,
                        document_observed_at,
                    ) in rows:
                        score = 1.0 - float(distance)
                        if score < similarity_threshold:
                            continue
                        items.append(
                            (chunk, score, document_created_at, document_observed_at)
                        )
                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": len(items),
                                "found": len(items) > 0,
                            }
                        )
                    return items
            result = await session.execute(stmt)
            rows = result.all()
            items = []
            for chunk, distance, document_created_at, document_observed_at in rows:
                score = 1.0 - float(distance)
                if score < similarity_threshold:
                    continue
                items.append((chunk, score, document_created_at, document_observed_at))
            return items

    async def get_tenant_rag_summary(
        self,
        *,
        tenant_id: UUID,
        configs_limit: int = 200,
    ) -> RagTenantSummaryData:
        async with self.db.get_session() as session:
            vs_cnt = await session.execute(
                select(func.count())
                .select_from(VectorStoreModel)
                .where(VectorStoreModel.tenant_id == tenant_id)
            )
            doc_cnt = await session.execute(
                select(func.count())
                .select_from(RagDocumentModel)
                .where(RagDocumentModel.tenant_id == tenant_id)
            )
            chunk_cnt = await session.execute(
                select(func.count())
                .select_from(RagChunkModel)
                .join(
                    RagDocumentModel,
                    RagChunkModel.document_id == RagDocumentModel.document_id,
                )
                .where(RagDocumentModel.tenant_id == tenant_id)
            )
            cfg_cnt = await session.execute(
                select(func.count())
                .select_from(RagConfigModel)
                .where(RagConfigModel.tenant_id == tenant_id)
            )
            cfg_rows = await session.execute(
                select(
                    RagConfigModel.rag_config_id,
                    RagConfigModel.status,
                    RagConfigModel.vector_store_id,
                    VectorStoreModel.name,
                )
                .join(
                    VectorStoreModel,
                    RagConfigModel.vector_store_id == VectorStoreModel.vector_store_id,
                )
                .where(RagConfigModel.tenant_id == tenant_id)
                .order_by(
                    VectorStoreModel.name.asc(),
                    RagConfigModel.version_major.desc(),
                    RagConfigModel.version_minor.desc(),
                    RagConfigModel.version_patch.desc(),
                )
                .limit(configs_limit)
            )
            configs = [
                RagConfigPreviewRow(
                    vector_store_id=row.vector_store_id,
                    name=row.name or "",
                    rag_config_id=row.rag_config_id,
                    status=str(row.status),
                )
                for row in cfg_rows.all()
            ]
            return RagTenantSummaryData(
                vector_stores_count=int(vs_cnt.scalar() or 0),
                documents_count=int(doc_cnt.scalar() or 0),
                chunks_count=int(chunk_cnt.scalar() or 0),
                rag_configs_count=int(cfg_cnt.scalar() or 0),
                configs=configs,
            )
