from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class McpServerUserPrompt(ORMBaseModel):
    __tablename__ = "mcp_server_user_prompt"

    mcp_server_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_server.mcp_server_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_prompt_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_prompt.user_prompt_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
