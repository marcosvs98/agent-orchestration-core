from sqlalchemy import Column, DateTime, ForeignKey, Index, Numeric, String, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentRun(ORMBaseModel):
    __tablename__ = "agent_run"

    agent_run_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent.agent_id", ondelete="RESTRICT"),
        nullable=False,
    )
    node_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_run.node_run_id", ondelete="CASCADE"),
        nullable=True,
    )
    agent_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_version.agent_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    ai_execution_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "ai_execution_policy_version.ai_execution_policy_version_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    model = Column(String(length=128), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Numeric(18, 6), nullable=True)
    billing_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("billing_policy_version.billing_policy_version_id", ondelete="RESTRICT"),
        nullable=True,
    )
    status = Column(String(length=32), nullable=False, server_default="CREATED")
    canonical_status = Column(String(length=32), nullable=False, server_default="CREATED")
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    input = Column(JSONB, nullable=False, server_default="{}")
    output = Column(JSONB, nullable=False, server_default="{}")
    error = Column(JSONB, nullable=False, server_default="{}")
    system_prompt_hash = Column(String(length=64), nullable=True)
    runtime_snapshot = Column(JSONB, nullable=False, server_default="{}")
    runtime_snapshot_hash = Column(String(length=64), nullable=True)

    origin = Column(String(length=32), nullable=False, server_default="FLOW_NODE")
    parent_agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    root_agent_run_id = Column(PG_UUID(as_uuid=True), nullable=True)
    delegation_depth = Column(Integer, nullable=False, server_default="0")
    context_snapshot = Column(JSONB, nullable=False, server_default="{}")
    tool_grant = Column(JSONB, nullable=False, server_default="{}")
    max_iterations = Column(Integer, nullable=True)
    iterations_used = Column(Integer, nullable=False, server_default="0")
    finish_reason = Column(String(length=64), nullable=True)
    idempotency_key = Column(String(length=255), nullable=True)

    __table_args__ = (
        Index("ix_agent_run_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_agent_run_root_agent_run_id", "root_agent_run_id"),
        Index("ix_agent_run_parent_agent_run_id", "parent_agent_run_id"),
        Index("ix_agent_run_agent_id", "agent_id"),
    )
