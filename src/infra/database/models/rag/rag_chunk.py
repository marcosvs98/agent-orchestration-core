from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from infra.database.models.base import ORMBaseModel, uuid_pk


class RagChunk(ORMBaseModel):
    """Store chunked content and embeddings for retrieval."""

    __tablename__ = "rag_chunk"

    chunk_id = uuid_pk()
    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_document.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text(), nullable=False)
    content_hash = Column(String(length=128), nullable=False)
    token_count = Column(Integer, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    embedding_512 = Column(Vector(512), nullable=True)
    embedding_model = Column(String(length=128), nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    chunk_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_rag_chunk_document_id_chunk_index",
        ),
        Index("ix_rag_chunk_document_id", "document_id"),
        Index("ix_rag_chunk_chunk_index", "chunk_index"),
        Index("ix_rag_chunk_embedding", "embedding", postgresql_using="ivfflat"),
    )
