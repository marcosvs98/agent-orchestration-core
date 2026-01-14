from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class RuntimePolicy(ORMBaseModel):
    __tablename__ = "runtime_policy"

    runtime_policy_id = uuid_pk()
    tenant_id = Column(PG_UUID(as_uuid=True), ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False)
    scope = Column(String(length=16), nullable=False)  # TENANT | FLOW
    flow_id = Column(PG_UUID(as_uuid=True), ForeignKey("flow.flow_id", ondelete="CASCADE"), nullable=True)
    version = Column(String(length=16), nullable=False, server_default="1")
    status = Column(String(length=16), nullable=False, server_default="DRAFT")  # DRAFT | ACTIVE
    policy_definition = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(length=128), nullable=False)
