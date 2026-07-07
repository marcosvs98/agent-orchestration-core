from __future__ import annotations

from domain.conversation.schemas.mcp_config import TenantMcpConfig


def build_conversation_mcp_tools(
    mcp_cfg: TenantMcpConfig,
    *,
    end_user_authorization: str | None,
) -> list[dict[str, str | dict[str, str]]]:
    headers: dict[str, str] = {"x-api-key": mcp_cfg.mcp_access_key}
    if isinstance(end_user_authorization, str) and end_user_authorization.strip():
        headers["authorization"] = end_user_authorization.strip()
    else:
        headers["authorization"] = f"Bearer {mcp_cfg.outbound_api_key}"
    return [
        {
            "type": "mcp",
            "server_label": "tenant-mcp",
            "server_url": mcp_cfg.mcp_server_url,
            "require_approval": "never",
            "headers": headers,
        }
    ]
