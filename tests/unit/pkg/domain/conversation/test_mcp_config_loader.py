from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from domain.conversation.schemas.mcp_config import TenantMcpConfig
from domain.conversation.services.mcp_config_loader import McpConfigLoader

_TENANT_ID = UUID("00000000-0000-0000-0000-000000000100")
_MCP_SERVER_ID = UUID("00000000-0000-0000-0000-000000001500")
_PUBLIC_BASE_URL = "https://mcp.example.com"


def _make_credential_row():
    row = MagicMock()
    row.mcp_server_id = _MCP_SERVER_ID
    row.mcp_access_key = "test-mcp-access-key"
    row.outbound_api_key = "test-outbound-api-key"
    return row


def _make_repo(row):
    repo = MagicMock()
    repo.find_active_for_tenant = AsyncMock(return_value=row)
    return repo


class TestMcpConfigLoader:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_credential(self):
        loader = McpConfigLoader(
            credential_repository=_make_repo(None),
            public_base_url=_PUBLIC_BASE_URL,
        )
        result = await loader.load_for_tenant(tenant_id=_TENANT_ID)
        assert result is None

    @pytest.mark.asyncio
    async def test_builds_correct_url(self):
        row = _make_credential_row()
        loader = McpConfigLoader(
            credential_repository=_make_repo(row),
            public_base_url=_PUBLIC_BASE_URL,
        )
        result = await loader.load_for_tenant(tenant_id=_TENANT_ID)
        assert result is not None
        expected_url = f"{_PUBLIC_BASE_URL}/core/v1/mcp-servers/{_MCP_SERVER_ID}/mcp"
        assert result.mcp_server_url == expected_url

    @pytest.mark.asyncio
    async def test_strips_trailing_slash_from_base_url(self):
        row = _make_credential_row()
        loader = McpConfigLoader(
            credential_repository=_make_repo(row),
            public_base_url=_PUBLIC_BASE_URL + "/",
        )
        result = await loader.load_for_tenant(tenant_id=_TENANT_ID)
        assert result is not None
        assert not result.mcp_server_url.startswith(_PUBLIC_BASE_URL + "//")

    @pytest.mark.asyncio
    async def test_returns_plaintext_keys(self):
        row = _make_credential_row()
        loader = McpConfigLoader(
            credential_repository=_make_repo(row),
            public_base_url=_PUBLIC_BASE_URL,
        )
        result = await loader.load_for_tenant(tenant_id=_TENANT_ID)
        assert result is not None
        assert result.mcp_access_key == "test-mcp-access-key"
        assert result.outbound_api_key == "test-outbound-api-key"

    @pytest.mark.asyncio
    async def test_returns_correct_mcp_server_id(self):
        row = _make_credential_row()
        loader = McpConfigLoader(
            credential_repository=_make_repo(row),
            public_base_url=_PUBLIC_BASE_URL,
        )
        result = await loader.load_for_tenant(tenant_id=_TENANT_ID)
        assert result is not None
        assert result.mcp_server_id == _MCP_SERVER_ID

    @pytest.mark.asyncio
    async def test_result_is_frozen(self):
        row = _make_credential_row()
        loader = McpConfigLoader(
            credential_repository=_make_repo(row),
            public_base_url=_PUBLIC_BASE_URL,
        )
        result = await loader.load_for_tenant(tenant_id=_TENANT_ID)
        assert isinstance(result, TenantMcpConfig)
        with pytest.raises(Exception):
            result.mcp_access_key = "mutated"  # type: ignore[misc]
