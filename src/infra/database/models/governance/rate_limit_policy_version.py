from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class RateLimitPolicyVersion(ORMBaseModel):
    __tablename__ = "rate_limit_policy_version"

    rate_limit_policy_version_id = uuid_pk()
    rate_limit_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rate_limit_policy.rate_limit_policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)

    action = Column(String(length=128), nullable=False)
    principal_type = Column(String(length=16), nullable=False)
    limit = Column(Integer, nullable=False)
    window_seconds = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "rate_limit_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_rate_limit_policy_version_semver",
        ),
        Index("ix_rate_limit_policy_version_status", "status"),
        Index("ix_rate_limit_policy_version_action", "action"),
    )
