from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.mcp_registry.controllers.mcp_registry_controller import (
    McpRegistryController,
)
from domain.mcp_registry.schemas.mcp_registry import (
    McpServerCreateRequest,
    McpServerCreateResponse,
)
from domain.mcp_registry.services.mcp_registry_service import McpRegistryService
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext


class TestMcpRegistryController:
    @pytest.fixture
    def service(self) -> MagicMock:
        svc = MagicMock(spec=McpRegistryService)
        svc.create_server = AsyncMock()
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
