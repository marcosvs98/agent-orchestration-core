from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class OnboardingVersion(ORMBaseModel):
    __tablename__ = "onboarding_version"

    onboarding_version_id = uuid_pk()
    onboarding_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("onboarding.onboarding_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint(
            "onboarding_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_onboarding_version_semver",
        ),
        Index("ix_onboarding_version_status", "status"),
    )
