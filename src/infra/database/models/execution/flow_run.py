from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class FlowRun(ORMBaseModel):
    __tablename__ = "flow_run"

    flow_run_id = uuid_pk()
    origin_flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    flow_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_version.flow_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("session.session_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = Column(String(length=255), nullable=False)
    interaction_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("interaction.interaction_id", ondelete="RESTRICT"),
        nullable=True,
    )
    status = Column(String(length=32), nullable=False, server_default="CREATED")
    canonical_status = Column(String(length=32), nullable=False, server_default="CREATED")
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    waiting_reason = Column(String(length=255), nullable=True)
    waiting_deadline_at = Column(DateTime(timezone=True), nullable=True)
    input = Column(JSONB, nullable=False, server_default="{}")
    output = Column(JSONB, nullable=False, server_default="{}")
    error = Column(JSONB, nullable=False, server_default="{}")
    flow_graph_snapshot_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_graph_snapshot.flow_graph_snapshot_id", ondelete="RESTRICT"),
        nullable=True,
    )
    flow_snapshot_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_snapshot.flow_snapshot_id", ondelete="RESTRICT"),
        nullable=True,
    )
    flow_deployment_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_deployment.flow_deployment_id", ondelete="RESTRICT"),
        nullable=True,
    )
    runtime_contract = Column(JSONB, nullable=False, server_default="{}")
    execution_plan_hash = Column(String(length=128), nullable=True)
    runtime_policy_hash = Column(String(length=128), nullable=True)
    tool_catalog_hash = Column(String(length=128), nullable=True)
    llm_provider_config_hash = Column(String(length=128), nullable=True)
    trace_id = Column(PG_UUID(as_uuid=True), nullable=True)
    root_observation_id = Column(String(length=128), nullable=True)
    temporal_workflow_id = Column(String(length=255), nullable=True)
    temporal_run_id = Column(String(length=64), nullable=True)
    turn_index = Column(Integer, nullable=False, server_default="0")
