from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class AuthoringEvent(ORMBaseModel):
    __tablename__ = "authoring_event"

    authoring_event_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    resource_type = Column(String(length=64), nullable=False)
    resource_id = Column(PG_UUID(as_uuid=True), nullable=False)
    version_id = Column(PG_UUID(as_uuid=True), nullable=True)
    event_type = Column(String(length=64), nullable=False)
    change_type = Column(String(length=64), nullable=False)
    principal_id = Column(String(length=128), nullable=False)
    justification = Column(String(length=512), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    schema_version = Column(Integer, nullable=False, server_default="1")
