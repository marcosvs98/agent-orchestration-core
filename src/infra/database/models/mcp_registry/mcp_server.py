from sqlalchemy import Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class McpServer(ORMBaseModel):
    __tablename__ = "mcp_server"

    mcp_server_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name = Column(String(length=255), nullable=False)
    status = Column(String(length=16), nullable=False, server_default="ACTIVE")
    config_version = Column(Integer, nullable=False, server_default="1")
    flow_snapshot_id = Column(PG_UUID(as_uuid=True), nullable=True)
    flow_deployment_id = Column(PG_UUID(as_uuid=True), nullable=True)
    server_metadata = Column("metadata", JSONB, nullable=True)

    __table_args__ = (Index("ix_mcp_server_tenant_id", "tenant_id"),)
