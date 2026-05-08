from contextvars import ContextVar

from domain.conversation.schemas.mcp_config import TenantMcpConfig

_CONVERSATION_MCP_CONFIG: ContextVar[TenantMcpConfig | None] = ContextVar(
    "conversation_mcp_config", default=None
)


def set_conversation_mcp_config(cfg: TenantMcpConfig | None) -> object:
    return _CONVERSATION_MCP_CONFIG.set(cfg)


def get_conversation_mcp_config() -> TenantMcpConfig | None:
    return _CONVERSATION_MCP_CONFIG.get()
