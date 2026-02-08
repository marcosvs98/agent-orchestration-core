from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select, update

from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.rag.rag_config import RagConfig as RagConfigModel
from infra.database.models.rag.rag_document import RagDocument as RagDocumentModel
from infra.database.models.rag.rag_chunk import RagChunk as RagChunkModel
from infra.database.models.rag.rag_query_cache import (
    RagQueryCache as RagQueryCacheModel,
)
from infra.database.models.rag.vector_store import VectorStore as VectorStoreModel


class RagRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_vector_store(self, vector_store_id: UUID) -> VectorStoreModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(VectorStoreModel).where(
                    VectorStoreModel.vector_store_id == vector_store_id
                )
            )
            return result.scalar_one_or_none()

    async def list_vector_stores(self) -> list[VectorStoreModel]:
        async with self.db.get_session() as session:
            stmt = select(VectorStoreModel).order_by(
                VectorStoreModel.name.asc().nulls_last(),
                VectorStoreModel.vector_store_id.asc(),
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_rag_config(self, rag_config_id: UUID) -> RagConfigModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RagConfigModel).where(
                    RagConfigModel.rag_config_id == rag_config_id
                )
            )
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
            result = await session.execute(
                select(RagDocumentModel).where(
                    RagDocumentModel.tenant_id == tenant_id,
                    RagDocumentModel.content_hash == content_hash,
                )
            )
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
    ) -> RagDocumentModel:
        async with self.db.get_session() as session:
            instance = RagDocumentModel(
                tenant_id=tenant_id,
                source=source,
                doc_type=doc_type,
                content_hash=content_hash,
                content=content,
                version=version,
                doc_metadata=metadata,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_documents(
        self, *, tenant_id: UUID, limit: int
    ) -> list[RagDocumentModel]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RagDocumentModel)
                .where(RagDocumentModel.tenant_id == tenant_id)
                .order_by(RagDocumentModel.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_chunks(
        self, *, document_id: UUID, limit: int
    ) -> list[RagChunkModel]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RagChunkModel)
                .where(RagChunkModel.document_id == document_id)
                .order_by(RagChunkModel.chunk_index.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def create_chunks(self, *, chunks: list[RagChunkModel]) -> None:
        async with self.db.get_session() as session:
            session.add_all(chunks)
            await session.commit()

    async def get_query_cache(
        self, *, tenant_id: UUID, query_hash: str
    ) -> RagQueryCacheModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RagQueryCacheModel).where(
                    RagQueryCacheModel.tenant_id == tenant_id,
                    RagQueryCacheModel.query_hash == query_hash,
                )
            )
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
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        filters: dict[str, object] | None,
    ) -> list[tuple[RagChunkModel, float]]:
        async with self.db.get_session() as session:
            stmt = (
                select(
                    RagChunkModel,
                    RagChunkModel.embedding.cosine_distance(query_embedding).label(
                        "distance"
                    ),
                )
                .join(
                    RagDocumentModel,
                    RagChunkModel.document_id == RagDocumentModel.document_id,
                )
                .where(RagDocumentModel.tenant_id == tenant_id)
            )
            if filters:
                if filters.get("source"):
                    stmt = stmt.where(RagDocumentModel.source == filters["source"])
                if filters.get("doc_type"):
                    stmt = stmt.where(RagDocumentModel.doc_type == filters["doc_type"])
            stmt = stmt.order_by(sa.text("distance asc")).limit(top_k)
            result = await session.execute(stmt)
            rows = result.all()
            items: list[tuple[RagChunkModel, float]] = []
            for chunk, distance in rows:
                score = 1.0 - float(distance)
                if score < similarity_threshold:
                    continue
                items.append((chunk, score))
            return items
