from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class OnboardingRun(ORMBaseModel):
    __tablename__ = "onboarding_run"

    onboarding_run_id = uuid_pk()
    onboarding_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("onboarding_version.onboarding_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
