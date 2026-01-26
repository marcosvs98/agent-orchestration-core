from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import func

from infra.database.models.base import ORMBaseModel, uuid_pk


class ExecutionEvent(ORMBaseModel):
    __tablename__ = "execution_event"

    execution_event_id = uuid_pk()
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
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
    causation_id = Column(PG_UUID(as_uuid=True), nullable=True)
    occurred_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    event_sequence = Column(BigInteger, nullable=False)
    schema_version = Column(Integer, nullable=False, server_default="1")
    type = Column(String(length=64), nullable=False)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    node_id = Column(PG_UUID(as_uuid=True), nullable=True)
    edge_id = Column(String(length=128), nullable=True)
