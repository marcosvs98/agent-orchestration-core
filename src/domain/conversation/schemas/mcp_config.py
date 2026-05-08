from uuid import UUID

from pydantic import BaseModel


class TenantMcpConfig(BaseModel):
    mcp_server_id: UUID
    mcp_server_url: str
    mcp_access_key: str
    outbound_api_key: str

    model_config = {"frozen": True}
