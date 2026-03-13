from uuid import UUID

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    external_id: UUID | None = None
    description: str | None = None
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True
    currency: str = "BRL"
    language: str = "pt_BR"
    contact_name: str | None = None
    contact_phone: str | None = None
    settings: dict[str, object] | None = None


class TenantCurrentResponse(BaseModel):
    id: UUID
    external_id: UUID | None = None
    name: str
    description: str | None = None
    timezone: str
    is_active: bool
    currency: str
    language: str
    contact_name: str | None = None
    contact_phone: str | None = None
    settings: dict[str, object] | None = None


class TenantResponse(BaseModel):
    id: UUID
    external_id: UUID | None = None
    name: str
    description: str | None = None
    timezone: str
    is_active: bool
    currency: str
    language: str
    contact_name: str | None = None
    contact_phone: str | None = None
    settings: dict[str, object] | None = None


class TenantSettingsResponse(BaseModel):
    id: UUID
    settings: dict[str, object] | None = None
