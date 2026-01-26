from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class LLMModelMapping(ORMBaseModel):
    __tablename__ = "llm_model_mapping"
    __mapper_args__ = {"exclude_properties": ["updated_at"]}

    llm_model_mapping_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(length=32), nullable=False)
    model_alias = Column(String(length=64), nullable=False)
    provider_model = Column(String(length=128), nullable=False)
    status = Column(String(length=16), nullable=False, server_default="ACTIVE")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(String(length=128), nullable=False)
