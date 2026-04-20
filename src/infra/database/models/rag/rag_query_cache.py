from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from infra.database.models.base import ORMBaseModel, uuid_pk


class RagQueryCache(ORMBaseModel):
    __tablename__ = "rag_query_cache"

    query_cache_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    vector_store_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vector_store.vector_store_id", ondelete="CASCADE"),
        nullable=False,
    )
    vector_store_version = Column(Integer, nullable=False, server_default="1")
    contract_hash = Column(String(length=64), nullable=False)
    query_hash = Column(String(length=128), nullable=False)
    embedding = Column(Vector(), nullable=True)
    use_count = Column(Integer, nullable=False, server_default="0")
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "vector_store_id",
            "vector_store_version",
            "contract_hash",
            "query_hash",
            name="uq_rag_query_cache_tenant_vector_store_version_hash_query_hash",
        ),
    )
