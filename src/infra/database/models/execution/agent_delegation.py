from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentDelegation(ORMBaseModel):
    """One A2A task delegated by a parent agent run to another agent."""

    __tablename__ = "agent_delegation"

    agent_delegation_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    child_agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    target_agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent.agent_id", ondelete="RESTRICT"),
        nullable=True,
    )
    transport = Column(String(length=32), nullable=False, server_default="internal")
    remote_endpoint = Column(Text(), nullable=True)
    a2a_task_id = Column(String(length=128), nullable=False)
    a2a_context_id = Column(String(length=128), nullable=False)
    a2a_task_state = Column(String(length=32), nullable=False, server_default="submitted")
    request_message = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    result = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "a2a_task_id", name="uq_agent_delegation_a2a_task"),
        Index("ix_agent_delegation_parent_agent_run_id", "parent_agent_run_id"),
        Index("ix_agent_delegation_a2a_context_id", "a2a_context_id"),
    )
