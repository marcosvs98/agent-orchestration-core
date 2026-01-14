from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class RunFailure(ORMBaseModel):
    __tablename__ = "run_failure"

    run_failure_id = uuid_pk()
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
        nullable=True,
    )
    node_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_run.node_run_id", ondelete="CASCADE"),
        nullable=True,
    )
    agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="CASCADE"),
        nullable=True,
    )
    tool_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tool_run.tool_run_id", ondelete="CASCADE"),
        nullable=True,
    )
    error_type = Column(String(length=64), nullable=False)
    error = Column(JSONB, nullable=False, server_default="{}")
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
