from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Tenant(ORMBaseModel):
    __tablename__ = "tenant"

    tenant_id = uuid_pk()
    external_id = Column(PG_UUID(as_uuid=True), nullable=True)
