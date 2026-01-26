from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class ActiveBillingPolicyVersion(ORMBaseModel):
    __tablename__ = "active_billing_policy_version"

    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    billing_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "billing_policy_version.billing_policy_version_id", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    activated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_by_principal_id = Column(String(length=128), nullable=False)
    justification = Column(String(length=512), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
