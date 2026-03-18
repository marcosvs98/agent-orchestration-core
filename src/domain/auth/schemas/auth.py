from uuid import UUID

from pydantic import BaseModel


class TenantTokenRequest(BaseModel):
    """Request body for issuing a tenant-scoped JWT."""

    tenant_id: UUID


class TenantTokenResponse(BaseModel):
    """Response body for tenant token issuance."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
