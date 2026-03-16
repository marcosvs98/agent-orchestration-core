from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class VectorStore(ORMBaseModel):
    __tablename__ = "vector_store"

    vector_store_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name = Column(String(length=255), nullable=False)
