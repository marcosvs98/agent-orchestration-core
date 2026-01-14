from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Escalation(ORMBaseModel):
    __tablename__ = "escalation"

    escalation_id = uuid_pk()
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    escalation_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("escalation_policy.escalation_policy_id", ondelete="RESTRICT"),
        nullable=False,
    )
