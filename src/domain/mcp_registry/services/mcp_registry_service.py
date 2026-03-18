from uuid import UUID

from adapters.observability.logging import get_logger
from domain.mcp_registry.repositories.mcp_registry_repository import (
    McpRegistryRepository,
)
from domain.mcp_registry.schemas.mcp_registry import (
    McpServerCreateRequest,
    McpServerCreateResponse,
)
from exceptions.service_exceptions import DomainValidationException

logger = get_logger(__name__)


class McpRegistryService:
    def __init__(
        self,
        repository: McpRegistryRepository,
        public_base_url: str,
    ) -> None:
        self.repository = repository
        self.public_base_url = public_base_url.rstrip("/")

    async def create_server(
        self,
        *,
        tenant_id: UUID,
        body: McpServerCreateRequest,
        endpoint_base: str | None = None,
    ) -> McpServerCreateResponse:
        ok_tools = await self.repository.validate_tool_configs_tenant(
            tenant_id=tenant_id, tool_config_ids=body.tool_config_ids
        )
        if not ok_tools:
            raise DomainValidationException(message="mcp_tool_config_tenant_mismatch")
        ok_vs = await self.repository.validate_vector_stores_tenant(
            tenant_id=tenant_id, vector_store_ids=body.vector_store_ids
        )
        if not ok_vs:
            raise DomainValidationException(message="mcp_vector_store_tenant_mismatch")
        ok_up = await self.repository.validate_user_prompts_tenant(
            tenant_id=tenant_id, user_prompt_ids=body.user_prompt_ids
        )
        if not ok_up:
            raise DomainValidationException(message="mcp_user_prompt_tenant_mismatch")
        name = body.name.strip() if body.name and body.name.strip() else "mcp-server"
        server, raw_key = await self.repository.create_server_with_bindings(
            tenant_id=tenant_id,
            name=name,
            tool_config_ids=body.tool_config_ids,
            vector_store_ids=body.vector_store_ids,
            user_prompt_ids=body.user_prompt_ids,
        )
        base = (endpoint_base or self.public_base_url).rstrip("/")
        endpoint = f"{base}/core/v1/mcp-servers/{server.mcp_server_id}/mcp"
        logger.info(
            "tenant_mcp_server_created",
            mcp_server_id=str(server.mcp_server_id),
            tenant_id=str(tenant_id),
            key_prefix=raw_key[:8] if len(raw_key) >= 8 else raw_key,
        )
        return McpServerCreateResponse(
            endpoint=endpoint,
            api_key=raw_key,
            mcp_server_id=server.mcp_server_id,
        )
