from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AccessPolicyVersion(ORMBaseModel):
    __tablename__ = "access_policy_version"

    access_policy_version_id = uuid_pk()
    access_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("access_policy.access_policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)
    rules = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint(
            "access_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_access_policy_version_semver",
        ),
        Index("ix_access_policy_version_status", "status"),
    )
