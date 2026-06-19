from __future__ import annotations

from typing import Any

from domain.conversation.schemas.mcp_config import TenantMcpConfig


def build_conversation_mcp_tools(
    mcp_cfg: TenantMcpConfig,
    metadata: dict[str, Any] | None,
) -> list[dict[str, str | dict[str, str]]]:
    headers: dict[str, str] = {"x-api-key": mcp_cfg.mcp_access_key}
    user_auth = (metadata or {}).get("uora_end_user_authorization")
    if isinstance(user_auth, str) and user_auth.strip():
        headers["authorization"] = user_auth.strip()
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
