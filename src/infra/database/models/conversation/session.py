from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Session(ORMBaseModel):
    __tablename__ = "session"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["end_user.tenant_id", "end_user.user_id"],
            ondelete="RESTRICT",
        ),
    )

    session_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = Column(String(length=255), nullable=False)
