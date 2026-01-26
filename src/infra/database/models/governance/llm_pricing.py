from sqlalchemy import Column, DateTime, Numeric, String, func

from infra.database.models.base import ORMBaseModel, uuid_pk


class LLMPricing(ORMBaseModel):
    __tablename__ = "llm_pricing"
    __mapper_args__ = {"exclude_properties": ["updated_at"]}

    llm_pricing_id = uuid_pk()
    provider = Column(String(length=32), nullable=False)
    provider_model = Column(String(length=128), nullable=False)
    unit = Column(String(length=16), nullable=False, server_default="tokens")
    input_cost_per_1k = Column(Numeric(18, 6), nullable=False)
    output_cost_per_1k = Column(Numeric(18, 6), nullable=False)
    currency = Column(String(length=8), nullable=False, server_default="USD")
    status = Column(String(length=16), nullable=False, server_default="ACTIVE")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(String(length=128), nullable=False)
