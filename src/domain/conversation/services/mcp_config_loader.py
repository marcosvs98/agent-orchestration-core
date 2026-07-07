from uuid import UUID

from domain.conversation.repositories.tenant_mcp_credential_repository import (
    TenantMcpCredentialRepository,
)
from domain.conversation.schemas.mcp_config import TenantMcpConfig


class McpConfigLoader:
    def __init__(
        self,
        credential_repository: TenantMcpCredentialRepository,
        public_base_url: str,
    ) -> None:
        self._repo = credential_repository
        self._public_base_url = public_base_url.rstrip("/")

    async def load_for_tenant(self, *, tenant_id: UUID) -> TenantMcpConfig | None:
        row = await self._repo.find_active_for_tenant(tenant_id=tenant_id)
        if row is None:
            return None
        mcp_server_url = f"{self._public_base_url}/core/v1/mcp-servers/{row.mcp_server_id}/mcp"
        return TenantMcpConfig(
            mcp_server_id=row.mcp_server_id,
            mcp_server_url=mcp_server_url,
            mcp_access_key=row.mcp_access_key,
            outbound_api_key=row.outbound_api_key,
        )
