from sqlalchemy import ARRAY, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Flow(ORMBaseModel):
    __tablename__ = "flow"

    flow_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name = Column(String(length=255), nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    created_by = Column(String(length=128), nullable=True)
