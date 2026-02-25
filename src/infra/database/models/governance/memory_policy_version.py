from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import text

from infra.database.models.base import ORMBaseModel, uuid_pk


class MemoryPolicyVersion(ORMBaseModel):
    __tablename__ = "memory_policy_version"

    memory_policy_version_id = uuid_pk()
    memory_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("memory_policy.memory_policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)
    retention_ttl_seconds = Column(Integer, nullable=False, server_default="2592000")
    consent_definition = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    allowed_sources = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    allowed_schemas = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    __table_args__ = (
        UniqueConstraint(
            "memory_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_memory_policy_version_semver",
        ),
        Index("ix_memory_policy_version_status", "status"),
    )
