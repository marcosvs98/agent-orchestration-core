from sqlalchemy import Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

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
    name = Column(String(length=255), nullable=False)
    status = Column(String(length=32), nullable=False, server_default="PENDING")
    input_payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    output_payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    schema_id = Column(PG_UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_step_run_status", "status"),
        Index("ix_step_run_onboarding_run_id", "onboarding_run_id"),
    )
