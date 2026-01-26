from sqlalchemy import Column, String

from infra.database.models.base import ORMBaseModel, uuid_pk


class VectorStore(ORMBaseModel):
    __tablename__ = "vector_store"

    vector_store_id = uuid_pk()
    name = Column(String(length=255), nullable=True)
