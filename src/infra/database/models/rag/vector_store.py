from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
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
    embedding_model = Column(String(length=128), nullable=False)
    embedding_dimension = Column(Integer(), nullable=False)
    metric = Column(String(length=32), nullable=False, server_default="cosine")
    version = Column(Integer(), nullable=False, server_default="1")
    active = Column(Boolean(), nullable=False, server_default="true")
