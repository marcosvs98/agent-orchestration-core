from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class HumanSLAEscalationRule(ORMBaseModel):
    __tablename__ = "human_sla_escalation_rule"

    human_sla_escalation_rule_id = uuid_pk()
    human_sla_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("human_sla_policy.human_sla_policy_id", ondelete="RESTRICT"),
        nullable=False,
    )
    level = Column(Integer, nullable=False)
    trigger_after_hours = Column(Integer, nullable=False)
    new_priority = Column(String(length=32), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "human_sla_policy_id",
            "level",
            name="uq_human_sla_escalation_rule_policy_level",
        ),
        CheckConstraint("level >= 0", name="ck_human_sla_escalation_rule_level_non_neg"),
        CheckConstraint(
            "trigger_after_hours >= 0",
            name="ck_human_sla_escalation_rule_trigger_non_neg",
        ),
    )
