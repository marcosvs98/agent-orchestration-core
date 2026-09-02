from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class TenantInboundServiceKey(ORMBaseModel):
    __tablename__ = "tenant_inbound_service_key"

    inbound_service_key_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    key_hash = Column(String(length=64), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("uq_tenant_inbound_service_key_hash", "key_hash", unique=True),)
