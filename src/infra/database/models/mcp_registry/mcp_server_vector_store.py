from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class McpServerVectorStore(ORMBaseModel):
    __tablename__ = "mcp_server_vector_store"

    mcp_server_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_server.mcp_server_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    vector_store_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vector_store.vector_store_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
