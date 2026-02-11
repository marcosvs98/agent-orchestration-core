from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class ActiveMemoryPolicyVersion(ORMBaseModel):
    __tablename__ = "active_memory_policy_version"

    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    memory_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("memory_policy_version.memory_policy_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    activated_by_principal_id = Column(String(length=128), nullable=False)
    justification = Column(String(length=512), nullable=False)
