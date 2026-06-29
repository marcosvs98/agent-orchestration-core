from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class NodeTemplate(ORMBaseModel):
    __tablename__ = "node_template"

    node_template_id = uuid_pk()
    code = Column(String(length=128), nullable=False, unique=True)
    node_type = Column(String(length=128), nullable=False)
    default_config = Column(JSONB, nullable=False)
    scope = Column(String(length=32), nullable=False, server_default="system")
    owner_tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, server_default="true")
