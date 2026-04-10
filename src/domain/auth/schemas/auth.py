from uuid import UUID

from pydantic import BaseModel, Field


class TenantTokenRequest(BaseModel):
    tenant_id: UUID | None = Field(default=None)


class TenantTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class InboundServiceKeyCreateRequest(BaseModel):
    tenant_id: UUID


class InboundServiceKeyCreateResponse(BaseModel):
    inbound_service_key_id: UUID
    tenant_id: UUID
    secret: str


class InboundServiceKeyRevokeRequest(BaseModel):
    tenant_id: UUID
