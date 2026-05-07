from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.mcp_registry.controllers.mcp_registry_controller import (
    McpRegistryController,
)
from domain.mcp_registry.schemas.mcp_registry import (
    McpServerCreateRequest,
    McpServerCreateResponse,
    McpServerDetail,
    McpServerPatchOutboundAuthRequest,
    McpServerSummary,
)
from domain.mcp_registry.services.mcp_registry_service import McpRegistryService
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext


class TestMcpRegistryController:
    @pytest.fixture
    def service(self) -> MagicMock:
        svc = MagicMock(spec=McpRegistryService)
        svc.create_server = AsyncMock()
        svc.list_servers = AsyncMock()
        svc.get_server = AsyncMock()
        svc.patch_mcp_server_outbound_auth = AsyncMock()
        return svc

    @pytest.fixture
    def controller(self, service: MagicMock) -> McpRegistryController:
        return McpRegistryController(service=service)

    @pytest.mark.asyncio
    async def test_create_returns_201_with_endpoint_and_key(
        self, controller: McpRegistryController, service: MagicMock
    ) -> None:
        tenant_id = uuid4()
        server_id = uuid4()
        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id="p1",
            scopes={"mcp_servers:create"},
            token_issuer="i",
            token_audience="a",
            expires_at=9999999999,
        )
        body_req = McpServerCreateRequest(
            tool_config_ids=[],
            vector_store_ids=[],
            user_prompt_ids=[],
            name="srv",
        )
        service.create_server = AsyncMock(
            return_value=McpServerCreateResponse(
                endpoint="https://api.example/core/v1/mcp-servers/x/mcp",
                api_key="secret-key-value",
                mcp_server_id=server_id,
            )
        )
        req = MagicMock()
        req.base_url = "http://localhost:8010/"

        result = await controller.create_mcp_server(
            body=body_req, request=req, auth=auth
        )
        assert isinstance(result, McpServerCreateResponse)
        assert result.api_key == "secret-key-value"
        assert result.mcp_server_id == server_id
        service.create_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_denied_without_scope(
        self, controller: McpRegistryController, service: MagicMock
    ) -> None:
        auth = AuthContext(
            tenant_id=uuid4(),
            principal_type="human",
            principal_id="p1",
            scopes={"flows:create"},
            token_issuer="i",
            token_audience="a",
            expires_at=9999999999,
        )
        body_req = McpServerCreateRequest(
            tool_config_ids=[],
            vector_store_ids=[],
            user_prompt_ids=[],
        )
        req = MagicMock()
        req.base_url = "http://localhost/"
        with pytest.raises(AuthorizationDeniedException, match="insufficient_scope"):
            await controller.create_mcp_server(
                body=body_req, request=req, auth=auth
            )
        service.create_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_denied_without_tenant_id(
        self, controller: McpRegistryController, service: MagicMock
    ) -> None:
        auth = AuthContext(
            tenant_id=None,
            principal_type="human",
            principal_id="p1",
            scopes={"mcp_servers:create"},
            token_issuer="i",
            token_audience="a",
            expires_at=9999999999,
        )
        body_req = McpServerCreateRequest(
            tool_config_ids=[],
            vector_store_ids=[],
            user_prompt_ids=[],
        )
        req = MagicMock()
        req.base_url = "http://localhost/"
        with pytest.raises(AuthorizationDeniedException, match="tenant_id_required"):
            await controller.create_mcp_server(
                body=body_req, request=req, auth=auth
            )
        service.create_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_returns_servers(
        self, controller: McpRegistryController, service: MagicMock
    ) -> None:
        tenant_id = uuid4()
        server_id = uuid4()
        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id="p1",
            scopes={"mcp_servers:list"},
            token_issuer="i",
            token_audience="a",
            expires_at=9999999999,
        )
        service.list_servers = AsyncMock(
            return_value=[
                McpServerSummary(
                    mcp_server_id=server_id,
                    name="srv",
                    status="ACTIVE",
                    endpoint="https://api.example/core/v1/mcp-servers/x/mcp",
                    flow_snapshot_id=None,
                    flow_deployment_id=None,
                )
            ]
        )
        result = await controller.list_mcp_servers(auth=auth)
        assert len(result) == 1
        assert result[0].mcp_server_id == server_id
        service.list_servers.assert_called_once_with(tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_get_returns_server_detail(
        self, controller: McpRegistryController, service: MagicMock
    ) -> None:
        tenant_id = uuid4()
        server_id = uuid4()
        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id="p1",
            scopes={"mcp_servers:get"},
            token_issuer="i",
            token_audience="a",
            expires_at=9999999999,
        )
        service.get_server = AsyncMock(
            return_value=                McpServerDetail(
                    mcp_server_id=server_id,
                    name="srv",
                    status="ACTIVE",
                    endpoint="https://api.example/core/v1/mcp-servers/x/mcp",
                    flow_snapshot_id=None,
                    flow_deployment_id=None,
                    tool_config_ids=[],
                    vector_store_ids=[],
                    user_prompt_ids=[],
                    outbound_authorization_fallback_configured=False,
                )
        )
        result = await controller.get_mcp_server(mcp_server_id=server_id, auth=auth)
        assert result.mcp_server_id == server_id
        service.get_server.assert_called_once_with(
            tenant_id=tenant_id, mcp_server_id=server_id
        )

    @pytest.mark.asyncio
    async def test_patch_outbound_auth_calls_service(
        self, controller: McpRegistryController, service: MagicMock
    ) -> None:
        tenant_id = uuid4()
        server_id = uuid4()
        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id="p1",
            scopes={"mcp_servers:create"},
            token_issuer="i",
            token_audience="a",
            expires_at=9999999999,
        )
        detail = McpServerDetail(
            mcp_server_id=server_id,
            name="srv",
            status="ACTIVE",
            endpoint="https://api.example/core/v1/mcp-servers/x/mcp",
            flow_snapshot_id=None,
            flow_deployment_id=None,
            tool_config_ids=[],
            vector_store_ids=[],
            user_prompt_ids=[],
            outbound_authorization_fallback_configured=True,
        )
        service.patch_mcp_server_outbound_auth = AsyncMock(return_value=detail)
        body = McpServerPatchOutboundAuthRequest(
            outbound_authorization_secret_ref="env:TEST_JWT",
        )
        result = await controller.patch_mcp_server_outbound_authorization(
            mcp_server_id=server_id, body=body, auth=auth
        )
        assert result.outbound_authorization_fallback_configured is True
        service.patch_mcp_server_outbound_auth.assert_called_once_with(
            tenant_id=tenant_id,
            mcp_server_id=server_id,
            body=body,
        )
