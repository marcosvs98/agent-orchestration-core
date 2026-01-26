from sqlalchemy import Column, String

from infra.database.models.base import ORMBaseModel, uuid_pk


class Tool(ORMBaseModel):
    __tablename__ = "tool"

    tool_id = uuid_pk()
    name = Column(String(length=255), nullable=True, unique=True)
