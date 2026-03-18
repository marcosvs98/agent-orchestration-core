from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class LLMProviderConfig(ORMBaseModel):
    __tablename__ = "llm_provider_config"
    __mapper_args__ = {"exclude_properties": ["updated_at"]}

    llm_provider_config_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(length=32), nullable=False)
    status = Column(String(length=16), nullable=False, server_default="INACTIVE")
    base_url = Column(Text(), nullable=True)
    credential_secret_ref = Column(Text(), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(String(length=128), nullable=False)

    __table_args__ = (
        Index(
            "ix_llm_provider_config_tenant_provider_status",
            "tenant_id",
            "provider",
            "status",
        ),
    )
