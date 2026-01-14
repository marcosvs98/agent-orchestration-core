from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class OnboardingStep(ORMBaseModel):
    __tablename__ = "onboarding_step"

    onboarding_step_id = uuid_pk()
    onboarding_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("onboarding_version.onboarding_version_id", ondelete="CASCADE"),
        nullable=False,
    )
