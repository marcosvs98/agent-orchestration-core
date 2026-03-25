from sqlalchemy import Boolean, Column, String

from infra.database.models.base import ORMBaseModel, uuid_pk


class Model(ORMBaseModel):
    __tablename__ = "model"

    model_id = uuid_pk()
    name = Column(String(length=255), nullable=False, unique=True)
    provider = Column(String(length=64), nullable=False)
    type = Column(String(length=32), nullable=False)
    is_active = Column(Boolean(), nullable=False, server_default="true")
