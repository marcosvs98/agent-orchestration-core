from sqlalchemy import Column, String

from infra.database.models.base import ORMBaseModel, uuid_pk


class Model(ORMBaseModel):
    __tablename__ = "model"

    model_id = uuid_pk()
    name = Column(String(length=255), nullable=False, unique=True)
