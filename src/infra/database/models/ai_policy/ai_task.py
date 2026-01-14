from sqlalchemy import Column, String

from infra.database.models.base import ORMBaseModel, uuid_pk


class AITask(ORMBaseModel):
    __tablename__ = "ai_task"

    ai_task_id = uuid_pk()
    name = Column(String(length=255), nullable=False, unique=True)
