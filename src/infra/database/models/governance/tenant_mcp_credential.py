from sqlalchemy import Column, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class TenantMcpCredential(ORMBaseModel):
    __tablename__ = "tenant_mcp_credential"

    tenant_mcp_credential_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    mcp_server_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_server.mcp_server_id", ondelete="CASCADE"),
        nullable=False,
    )
    mcp_access_key = Column(Text, nullable=False)
    outbound_api_key = Column(Text, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_tenant_mcp_credential_tenant_active",
            "tenant_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
