from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class McpServerTool(ORMBaseModel):
    __tablename__ = "mcp_server_tool"

    mcp_server_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_server.mcp_server_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    tool_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tool_config.tool_config_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
