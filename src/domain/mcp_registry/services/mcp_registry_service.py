from uuid import UUID

from adapters.observability.logging import get_logger
from domain.mcp_registry.mcp_server_metadata import (
    outbound_authorization_secret_ref_from_server_metadata,
)
from domain.mcp_registry.repositories.mcp_registry_repository import (
    McpRegistryRepository,
)
from domain.mcp_registry.schemas.mcp_registry import (
    McpServerCreateRequest,
    McpServerCreateResponse,
    McpServerDetail,
    McpServerPatchOutboundAuthRequest,
    McpServerSummary,
)
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)

logger = get_logger(__name__)


def _normalize_outbound_authorization_secret_ref(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if not s.startswith("env:"):
        raise DomainValidationException(
            message="mcp_outbound_authorization_secret_ref_must_use_env_prefix",
        )
    return s


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
        ok_snapshot = await self.repository.validate_flow_snapshot_tenant(
            tenant_id=tenant_id, flow_snapshot_id=body.flow_snapshot_id
        )
        if not ok_snapshot:
            raise DomainValidationException(message="mcp_flow_snapshot_tenant_mismatch")
        ok_deployment = await self.repository.validate_flow_deployment_tenant(
            tenant_id=tenant_id, flow_deployment_id=body.flow_deployment_id
        )
        if not ok_deployment:
            raise DomainValidationException(message="mcp_flow_deployment_tenant_mismatch")
        name = body.name.strip() if body.name and body.name.strip() else "mcp-server"
        ob_ref = _normalize_outbound_authorization_secret_ref(
            body.outbound_authorization_secret_ref
        )
        server_metadata: dict[str, object] | None = None
        if ob_ref:
            server_metadata = {"outbound_authorization_secret_ref": ob_ref}
        server, raw_key = await self.repository.create_server_with_bindings(
            tenant_id=tenant_id,
            name=name,
            tool_config_ids=body.tool_config_ids,
            vector_store_ids=body.vector_store_ids,
            user_prompt_ids=body.user_prompt_ids,
            flow_snapshot_id=body.flow_snapshot_id,
            flow_deployment_id=body.flow_deployment_id,
            server_metadata=server_metadata,
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

    async def list_servers(self, *, tenant_id: UUID) -> list[McpServerSummary]:
        servers = await self.repository.list_servers_by_tenant(tenant_id=tenant_id)
        base = self.public_base_url.rstrip("/")
        return [
            McpServerSummary(
                mcp_server_id=server.mcp_server_id,
                name=server.name,
                status=server.status,
                endpoint=f"{base}/core/v1/mcp-servers/{server.mcp_server_id}/mcp",
                flow_snapshot_id=server.flow_snapshot_id,
                flow_deployment_id=server.flow_deployment_id,
            )
            for server in servers
        ]

    async def get_server(self, *, tenant_id: UUID, mcp_server_id: UUID) -> McpServerDetail:
        server = await self.repository.get_server_by_tenant(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
        )
        if server is None:
            raise NotFoundServiceException(message="mcp_server_not_found")
        (
            tool_ids,
            vector_store_ids,
            user_prompt_ids,
        ) = await self.repository.list_server_binding_ids(mcp_server_id=mcp_server_id)
        base = self.public_base_url.rstrip("/")
        ob = outbound_authorization_secret_ref_from_server_metadata(server.server_metadata)
        return McpServerDetail(
            mcp_server_id=server.mcp_server_id,
            name=server.name,
            status=server.status,
            endpoint=f"{base}/core/v1/mcp-servers/{server.mcp_server_id}/mcp",
            flow_snapshot_id=server.flow_snapshot_id,
            flow_deployment_id=server.flow_deployment_id,
            tool_config_ids=tool_ids,
            vector_store_ids=vector_store_ids,
            user_prompt_ids=user_prompt_ids,
            outbound_authorization_fallback_configured=bool(ob),
        )

    async def patch_mcp_server_outbound_auth(
        self,
        *,
        tenant_id: UUID,
        mcp_server_id: UUID,
        body: McpServerPatchOutboundAuthRequest,
    ) -> McpServerDetail:
        ref = _normalize_outbound_authorization_secret_ref(body.outbound_authorization_secret_ref)
        ok = await self.repository.patch_mcp_server_outbound_authorization_secret_ref(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            outbound_authorization_secret_ref=ref,
        )
        if not ok:
            raise NotFoundServiceException(message="mcp_server_not_found")
        from adapters.mcp.tenant_mcp_gateway import clear_tenant_mcp_app_cache

        clear_tenant_mcp_app_cache()
        return await self.get_server(tenant_id=tenant_id, mcp_server_id=mcp_server_id)
