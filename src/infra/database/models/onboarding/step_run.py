from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class StepRun(ORMBaseModel):
    __tablename__ = "step_run"

    step_run_id = uuid_pk()
    onboarding_step_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("onboarding_step.onboarding_step_id", ondelete="CASCADE"),
        nullable=False,
    )
    onboarding_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("onboarding_run.onboarding_run_id", ondelete="CASCADE"),
        nullable=False,
    )
