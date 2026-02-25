from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import text

from infra.database.models.base import ORMBaseModel, uuid_pk


class RagPolicyVersion(ORMBaseModel):
    __tablename__ = "rag_policy_version"

    rag_policy_version_id = uuid_pk()
    rag_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_policy.rag_policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)
    policy_definition = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        UniqueConstraint(
            "rag_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_rag_policy_version_semver",
        ),
        Index("ix_rag_policy_version_status", "status"),
    )
