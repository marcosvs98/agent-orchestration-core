from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentRun(ORMBaseModel):
    __tablename__ = "agent_run"

    agent_run_id = uuid_pk()
    ai_task_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_task.ai_task_id", ondelete="RESTRICT"),
        nullable=True,
    )
    node_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_run.node_run_id", ondelete="CASCADE"),
        nullable=False,
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
        nullable=False,
    )
    model = Column(String(length=128), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Numeric(18, 6), nullable=True)
    billing_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "billing_policy_version.billing_policy_version_id", ondelete="RESTRICT"
        ),
        nullable=True,
    )
    status = Column(String(length=32), nullable=False, server_default="CREATED")
    canonical_status = Column(
        String(length=32), nullable=False, server_default="CREATED"
    )
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    input = Column(JSONB, nullable=False, server_default="{}")
    output = Column(JSONB, nullable=False, server_default="{}")
    error = Column(JSONB, nullable=False, server_default="{}")
    system_prompt_hash = Column(String(length=64), nullable=True)