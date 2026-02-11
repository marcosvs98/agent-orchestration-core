from sqlalchemy import Column, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class UserPreference(ORMBaseModel):
    __tablename__ = "user_preference"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["end_user.tenant_id", "end_user.user_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "preference_key",
            name="uq_user_preference_key",
        ),
    )

    user_preference_id = uuid_pk()
    tenant_id = Column(PG_UUID(as_uuid=True), nullable=False)
    user_id = Column(String(length=255), nullable=False)
    preference_key = Column(String(length=128), nullable=False)
    preference_value = Column(JSONB, nullable=False)
    source = Column(String(length=32), nullable=False)
    version = Column(Integer, nullable=False, server_default="1")
