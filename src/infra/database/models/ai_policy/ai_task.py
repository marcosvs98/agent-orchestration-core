from sqlalchemy import Boolean, Column, String

from infra.database.models.base import ORMBaseModel, uuid_pk


class AITask(ORMBaseModel):
    __tablename__ = "ai_task"

    ai_task_id = uuid_pk()
    name = Column(String(length=255), nullable=False, unique=True)
    allow_rag_tenant = Column(Boolean, nullable=False, server_default="false")
    allow_user_memory = Column(Boolean, nullable=False, server_default="false")
    allow_session_context = Column(Boolean, nullable=False, server_default="false")
    allow_memory_write = Column(Boolean, nullable=False, server_default="false")
