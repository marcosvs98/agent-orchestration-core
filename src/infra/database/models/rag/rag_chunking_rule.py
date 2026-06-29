from sqlalchemy import Column, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class RagChunkingRule(ORMBaseModel):
    __tablename__ = "rag_chunking_rule"

    rag_chunking_rule_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name = Column(String(length=255), nullable=False)
    status = Column(String(length=16), nullable=False, server_default="ACTIVE")
    strategy = Column(String(length=64), nullable=False)
    params = Column(JSONB, nullable=False)
    config_hash = Column(String(length=128), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_rag_chunking_rule_tenant_name"),
        Index("ix_rag_chunking_rule_tenant_id", "tenant_id"),
    )
