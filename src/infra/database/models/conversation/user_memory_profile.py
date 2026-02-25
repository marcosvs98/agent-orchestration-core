from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class UserMemoryProfile(ORMBaseModel):
    __tablename__ = "user_memory_profile"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["end_user.tenant_id", "end_user.user_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "user_id", name="uq_user_memory_profile_user"),
    )

    user_memory_profile_id = uuid_pk()
    tenant_id = Column(PG_UUID(as_uuid=True), nullable=False)
    user_id = Column(String(length=255), nullable=False)
    profile = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    profile_version = Column(Integer, nullable=False, server_default="1")
