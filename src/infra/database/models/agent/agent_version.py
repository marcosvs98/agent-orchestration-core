from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentVersion(ORMBaseModel):
    __tablename__ = "agent_version"

    agent_version_id = uuid_pk()
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent.agent_id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_execution_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "ai_execution_policy_version.ai_execution_policy_version_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    rag_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_config.rag_config_id", ondelete="RESTRICT"),
        nullable=True,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)
    description = Column(Text(), nullable=True)

    supported_tool_schema_version = Column(Integer, nullable=True)
    supported_tool_config_hash_prefix = Column(String(length=128), nullable=True)
    persona_config = Column(JSONB, nullable=True)
    system_prompt = Column(Text(), nullable=True)
    is_active = Column(Boolean(), nullable=False, server_default="false")
    activated_at = Column(DateTime(timezone=True), nullable=True)
    activated_by_principal_id = Column(String(length=128), nullable=True)
    justification = Column(String(length=512), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_agent_version_semver",
        ),
        Index("ix_agent_version_status", "status"),
    )
