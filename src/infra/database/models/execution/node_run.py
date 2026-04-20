from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class NodeRun(ORMBaseModel):
    __tablename__ = "node_run"

    node_run_id = uuid_pk()
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node.node_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(length=32), nullable=False, server_default="CREATED")
    canonical_status = Column(String(length=32), nullable=False, server_default="PENDING")
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    input = Column(JSONB, nullable=False, server_default="{}")
    output = Column(JSONB, nullable=False, server_default="{}")
    error = Column(JSONB, nullable=False, server_default="{}")
