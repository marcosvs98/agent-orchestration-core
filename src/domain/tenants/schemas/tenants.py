from uuid import UUID

from pydantic import BaseModel


class TenantCurrentResponse(BaseModel):
    id: UUID
    external_id: UUID | None = None


class TenantSettingsResponse(BaseModel):
    id: UUID
    settings: dict[str, object] | None = None
