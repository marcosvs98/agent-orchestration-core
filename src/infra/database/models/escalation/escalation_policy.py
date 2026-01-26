from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class EscalationPolicy(ORMBaseModel):
    __tablename__ = "escalation_policy"

    escalation_policy_id = uuid_pk()
    condition_expression_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("condition_expression.condition_expression_id", ondelete="RESTRICT"),
        nullable=True,
    )
