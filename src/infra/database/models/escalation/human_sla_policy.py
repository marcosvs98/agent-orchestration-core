from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class HumanSLAPolicy(ORMBaseModel):
    __tablename__ = "human_sla_policy"

    human_sla_policy_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name = Column(String(length=128), nullable=False)
    node = Column(String(length=64), nullable=False)
    fallback_reason = Column(String(length=64), nullable=False)
    initial_priority = Column(String(length=32), nullable=False)
    target_response_hours = Column(Integer, nullable=True)
    target_resolution_hours = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        Index("ix_human_sla_policy_tenant_node_reason", "tenant_id", "node", "fallback_reason"),
        CheckConstraint(
            "target_response_hours IS NULL OR target_response_hours > 0",
            name="ck_human_sla_policy_target_response_hours_positive",
        ),
        CheckConstraint(
            "target_resolution_hours IS NULL OR target_resolution_hours > 0",
            name="ck_human_sla_policy_target_resolution_hours_positive",
        ),
    )
