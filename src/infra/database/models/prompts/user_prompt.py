from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class UserPrompt(ORMBaseModel):
    __tablename__ = "user_prompt"

    user_prompt_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    title = Column(String(length=255), nullable=False)
    content = Column(Text(), nullable=False)
    version = Column(Integer(), nullable=False, server_default="1")
    is_active = Column(Boolean(), nullable=False, server_default="true")
    created_by = Column(String(length=128), nullable=True)
