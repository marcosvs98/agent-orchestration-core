from __future__ import annotations

from uuid import uuid4

from domain.conversation.schemas.mcp_config import TenantMcpConfig
from domain.conversation.services.conversation_mcp_tools import build_conversation_mcp_tools


def test_build_conversation_mcp_tools_uses_end_user_authorization() -> None:
    cfg = TenantMcpConfig(
        mcp_server_id=uuid4(),
        mcp_server_url="http://example.com/core/v1/mcp-servers/x/mcp",
        mcp_access_key="mcp-access-key",
        outbound_api_key="outbound-fallback",
    )
    tools = build_conversation_mcp_tools(
        cfg,
        {"uora_end_user_authorization": "Bearer user-jwt"},
    )
    assert tools[0]["headers"]["x-api-key"] == "mcp-access-key"
    assert tools[0]["headers"]["authorization"] == "Bearer user-jwt"


def test_build_conversation_mcp_tools_falls_back_to_outbound_key() -> None:
    cfg = TenantMcpConfig(
        mcp_server_id=uuid4(),
        mcp_server_url="http://example.com/core/v1/mcp-servers/x/mcp",
        mcp_access_key="mcp-access-key",
        outbound_api_key="outbound-fallback",
    )
    tools = build_conversation_mcp_tools(cfg, {})
    assert tools[0]["headers"]["authorization"] == "Bearer outbound-fallback"
