from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class ActiveAgentVersion(ORMBaseModel):
    __tablename__ = "active_agent_version"

    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent.agent_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    agent_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_version.agent_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    activated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_by_principal_id = Column(String(length=128), nullable=False)
    justification = Column(String(length=512), nullable=False)
