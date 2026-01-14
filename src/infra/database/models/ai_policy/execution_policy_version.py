from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AIExecutionPolicyVersion(ORMBaseModel):
    __tablename__ = "ai_execution_policy_version"

    ai_execution_policy_version_id = uuid_pk()
    ai_execution_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_execution_policy.ai_execution_policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    model_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("model.model_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ai_execution_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_ai_policy_version_semver",
        ),
        Index("ix_ai_policy_version_status", "status"),
    )