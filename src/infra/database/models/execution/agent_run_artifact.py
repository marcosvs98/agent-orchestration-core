from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentRunArtifact(ORMBaseModel):
    __tablename__ = "agent_run_artifact"

    agent_run_artifact_id = uuid_pk()
    agent_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_run.agent_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_index = Column(Integer, nullable=False)
    name = Column(String(length=255), nullable=True)
    description = Column(Text(), nullable=True)
    parts = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    schema_version = Column(Integer, nullable=False, server_default="1")

    __table_args__ = (
        UniqueConstraint(
            "agent_run_id",
            "artifact_index",
            name="uq_agent_run_artifact_index",
        ),
    )
