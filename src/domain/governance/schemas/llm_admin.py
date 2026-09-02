from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ProviderUpsertRequest(BaseModel):
    tenant_id: UUID
    provider: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=32)
    base_url: str | None = None
    credential_secret_ref: str | None = None


class ModelMappingUpsertRequest(BaseModel):
    tenant_id: UUID
    provider: str = Field(min_length=1, max_length=64)
    model_alias: str = Field(min_length=1, max_length=128)
    provider_model: str = Field(min_length=1, max_length=128)
    status: str = Field(default="ACTIVE", min_length=1, max_length=32)


class PricingUpsertRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    provider_model: str = Field(min_length=1, max_length=128)
    unit: str = Field(min_length=1, max_length=32)
    input_cost_per_1k: float = Field(ge=0)
    output_cost_per_1k: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: str = Field(default="ACTIVE", min_length=1, max_length=32)
