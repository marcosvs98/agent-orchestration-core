from sqlalchemy import Boolean, Column, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Tenant(ORMBaseModel):
    __tablename__ = "tenant"

    tenant_id = uuid_pk()
    external_id = Column(PG_UUID(as_uuid=True), nullable=True)
    name = Column(String(length=255), nullable=False)
    description = Column(Text, nullable=True)
    timezone = Column(
        String(length=64), nullable=False, server_default="America/Sao_Paulo"
    )
    is_active = Column(Boolean, nullable=False, server_default="true")
    currency = Column(String(length=3), nullable=False, server_default="BRL")
    language = Column(String(length=10), nullable=False, server_default="pt_BR")
    contact_name = Column(String(length=255), nullable=True)
    contact_phone = Column(String(length=50), nullable=True)
    settings = Column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_tenant_external_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )
