from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from infra.database.models.base import ORMBaseModel, uuid_pk


class NodePrompt(ORMBaseModel):
    __tablename__ = "node_prompt"

    prompt_id = uuid_pk()
    node_type = Column(String(length=64), nullable=False)
    template_text = Column(Text(), nullable=False)
    output_schema = Column(JSONB, nullable=True)
    version = Column(Integer(), nullable=False)
    frozen_hash = Column(String(length=64), nullable=False)
    is_active = Column(Boolean(), nullable=False, server_default="true")
    description = Column(Text(), nullable=True)
    created_by = Column(String(length=128), nullable=True)
