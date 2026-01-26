from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class ToolRun(ORMBaseModel):
    __tablename__ = "tool_run"

    tool_run_id = uuid_pk()
    agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    node_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_run.node_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tool_config.tool_config_id", ondelete="RESTRICT"),
        nullable=False,
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
    idempotency_key = Column(String(length=255), nullable=True)
    has_side_effect = Column(Boolean, nullable=False, server_default="false")
    estimated_cost = Column(Numeric(18, 6), nullable=True)
    billing_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "billing_policy_version.billing_policy_version_id", ondelete="RESTRICT"
        ),
        nullable=True,
    )
