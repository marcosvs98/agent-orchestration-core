from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentRunMessage(ORMBaseModel):
    __tablename__ = "agent_run_message"

    agent_run_message_id = uuid_pk()
    agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    message_sequence = Column(Integer, nullable=False)
    role = Column(String(length=16), nullable=False)
    content = Column(Text(), nullable=True)
    tool_call_id = Column(String(length=128), nullable=True)
    tool_name = Column(String(length=255), nullable=True)
    tool_calls = Column(JSONB, nullable=False, server_default="[]")
    trust_level = Column(String(length=32), nullable=True)
    source = Column(String(length=64), nullable=True)
    provenance = Column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        UniqueConstraint(
            "agent_run_id",
            "message_sequence",
            name="uq_agent_run_message_sequence",
        ),
    )
