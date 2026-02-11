from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class ActiveRagPolicyVersion(ORMBaseModel):
    __tablename__ = "active_rag_policy_version"

    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    rag_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_policy_version.rag_policy_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    activated_by_principal_id = Column(String(length=128), nullable=False)
    justification = Column(String(length=512), nullable=False)
