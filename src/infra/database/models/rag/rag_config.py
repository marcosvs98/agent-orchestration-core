from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class RagConfig(ORMBaseModel):
    __tablename__ = "rag_config"

    rag_config_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    vector_store_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vector_store.vector_store_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_rag_config_semver",
        ),
        Index("ix_rag_config_status", "status"),
    )