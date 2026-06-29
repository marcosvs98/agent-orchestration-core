from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class RagUsageCounter(ORMBaseModel):
    __tablename__ = "rag_usage_counter"

    rag_usage_counter_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    scope = Column(String(length=16), nullable=False)
    user_id = Column(String(length=255), nullable=True)
    rag_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_config.rag_config_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_count = Column(Integer, nullable=False, server_default="0")
    chunk_count = Column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        CheckConstraint(
            "(scope = 'TENANT' AND user_id IS NULL) OR "
            "(scope = 'USER' AND user_id IS NOT NULL)",
            name="ck_rag_usage_counter_scope_user",
        ),
        CheckConstraint(
            "document_count >= 0 AND chunk_count >= 0",
            name="ck_rag_usage_counter_counts_non_negative",
        ),
        Index("ix_rag_usage_counter_tenant_id", "tenant_id"),
    )
