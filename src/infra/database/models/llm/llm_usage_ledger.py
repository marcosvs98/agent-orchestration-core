from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class LLMUsageLedger(ORMBaseModel):
    __tablename__ = "llm_usage_ledger"

    llm_usage_ledger_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
        nullable=True,
    )
    node_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_run.node_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id = Column(PG_UUID(as_uuid=True), nullable=True)
    provider = Column(String(length=64), nullable=True)
    provider_model = Column(String(length=128), nullable=True)
    task_type = Column(String(length=64), nullable=True)
    inference_layer = Column(String(length=32), nullable=True)
    input_tokens = Column(Integer, nullable=False, server_default="0")
    output_tokens = Column(Integer, nullable=False, server_default="0")
    cost_usd = Column(Numeric(18, 6), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_llm_usage_ledger_tenant_id_occurred_at", "tenant_id", "occurred_at"),
        Index("ix_llm_usage_ledger_flow_run_id", "flow_run_id"),
    )
