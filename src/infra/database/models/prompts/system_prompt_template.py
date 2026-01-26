from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from infra.database.models.base import ORMBaseModel, uuid_pk


class SystemPromptTemplate(ORMBaseModel):
    __tablename__ = "system_prompt_template"

    template_id = uuid_pk()
    name = Column(String(length=255), nullable=False)
    template_text = Column(Text(), nullable=False)
    allowed_placeholders = Column(JSONB, nullable=True)
    version = Column(Integer(), nullable=False, server_default="1")
    status = Column(String(length=32), nullable=False, server_default="DRAFT")
    description = Column(Text(), nullable=True)
