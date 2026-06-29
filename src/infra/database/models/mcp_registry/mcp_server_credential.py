from sqlalchemy import Column, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class McpServerCredential(ORMBaseModel):
    __tablename__ = "mcp_server_credential"

    credential_id = uuid_pk()
    mcp_server_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_server.mcp_server_id", ondelete="CASCADE"),
        nullable=False,
    )
    key_hash = Column(String(length=128), nullable=False)
    key_prefix = Column(String(length=16), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_mcp_server_credential_mcp_server_id", "mcp_server_id"),
        Index(
            "uq_mcp_credential_active_per_server",
            "mcp_server_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
