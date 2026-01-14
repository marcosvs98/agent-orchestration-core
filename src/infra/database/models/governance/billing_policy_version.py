from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class BillingPolicyVersion(ORMBaseModel):
    __tablename__ = "billing_policy_version"

    billing_policy_version_id = uuid_pk()
    billing_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("billing_policy.billing_policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=32), nullable=False)
    version_major = Column(Integer, nullable=False, default=1)
    version_minor = Column(Integer, nullable=False, default=0)
    version_patch = Column(Integer, nullable=False, default=0)
    config_hash = Column(String(length=128), nullable=True)
    rules = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
