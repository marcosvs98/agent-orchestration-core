from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class User(ORMBaseModel):
    __tablename__ = "end_user"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_end_user_tenant_user"),
    )

    end_user_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = Column(String(length=255), nullable=False)
