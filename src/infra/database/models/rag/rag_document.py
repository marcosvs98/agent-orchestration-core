from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import func

from infra.database.models.base import ORMBaseModel, uuid_pk


class RagDocument(ORMBaseModel):
    """Store documents ingested into the RAG pipeline."""

    __tablename__ = "rag_document"

    document_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    rag_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_config.rag_config_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source = Column(String(length=255), nullable=True)
    doc_type = Column(String(length=128), nullable=True)
    content_hash = Column(String(length=128), nullable=False)
    content = Column(Text(), nullable=True)
    version = Column(String(length=64), nullable=True)
    embedding_status = Column(
        String(length=32), nullable=False, server_default="PENDING"
    )
    embedding_attempts = Column(Integer, nullable=False, server_default="0")
    last_embedding_error_code = Column(String(length=128), nullable=True)
    embedding_started_at = Column(DateTime(timezone=True), nullable=True)
    embedding_completed_at = Column(DateTime(timezone=True), nullable=True)
    doc_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "content_hash",
            name="uq_rag_document_tenant_id_content_hash",
        ),
    )
