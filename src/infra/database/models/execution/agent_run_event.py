from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import func

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentRunEvent(ORMBaseModel):
    __tablename__ = "agent_run_event"

    agent_run_event_id = uuid_pk()
    agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    type = Column(Text(), nullable=False)
    event_sequence = Column(BigInteger, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
    causation_id = Column(PG_UUID(as_uuid=True), nullable=True)
    schema_version = Column(Integer, nullable=False, server_default="1")
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint(
            "agent_run_id",
            "event_sequence",
            name="uq_agent_run_event_sequence",
        ),
        Index("ix_agent_run_event_tenant_id_occurred_at", "tenant_id", "occurred_at"),
    )
