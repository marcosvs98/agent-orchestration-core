from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AgentVersionToolBinding(ORMBaseModel):
    __tablename__ = "agent_version_tool_binding"

    agent_version_tool_binding_id = uuid_pk()
    agent_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_version.agent_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tool_config.tool_config_id", ondelete="CASCADE"),
        nullable=False,
    )
