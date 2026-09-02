from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class SLACase(ORMBaseModel):
    __tablename__ = "sla_case"

    sla_case_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("session.session_id", ondelete="RESTRICT"),
        nullable=False,
    )
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    node_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_run.node_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("interaction.interaction_id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id = Column(String(length=255), nullable=False)
    status = Column(String(length=32), nullable=False, server_default="OPEN")
    priority = Column(String(length=32), nullable=True)
    fallback_reason = Column(Text, nullable=False)
    human_agent_id = Column(String(length=128), nullable=True)
    resolution_status = Column(String(length=32), nullable=True)
    resolution_summary = Column(Text, nullable=True)
    human_sla_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("human_sla_policy.human_sla_policy_id", ondelete="RESTRICT"),
        nullable=True,
    )
    current_escalation_level = Column(Integer, nullable=False, server_default="0")
    opened_at = Column(DateTime(timezone=True), nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    sla_target_at = Column(DateTime(timezone=True), nullable=True)
    sla_breached = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        UniqueConstraint("flow_run_id", "node_run_id", name="uq_sla_case_flow_run_node_run"),
        CheckConstraint(
            "current_escalation_level >= 0",
            name="ck_sla_case_current_escalation_level_non_neg",
        ),
        Index("ix_sla_case_tenant_status", "tenant_id", "status"),
        Index("ix_sla_case_session", "session_id"),
        Index("ix_sla_case_flow_run", "flow_run_id"),
        Index("ix_sla_case_opened_at", "opened_at"),
        Index("ix_sla_case_sla_target_at", "sla_target_at"),
        Index("ix_sla_case_human_sla_policy_id", "human_sla_policy_id"),
    )
