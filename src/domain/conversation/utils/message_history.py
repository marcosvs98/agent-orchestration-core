from __future__ import annotations

from domain.common.interaction_metadata import (
    ACCEPTED_END_USER_AUTHORIZATION_METADATA_KEYS,
)

_FORBIDDEN_METADATA_KEYS = set(ACCEPTED_END_USER_AUTHORIZATION_METADATA_KEYS) | {
    "tenant_id",
    "user_id",
    "current_date",
    "mcp_server_url",
    "headers",
}
_MAX_HISTORY_ITEMS = 50
_MAX_MESSAGE_CONTENT_LENGTH = 16000


def parse_message_history(metadata: dict[str, object] | None) -> list[dict[str, str]]:
    if not metadata:
        return []
    for key in _FORBIDDEN_METADATA_KEYS:
        if key in metadata:
            raise ValueError(f"forbidden_metadata_key:{key}")
    raw = metadata.get("message_history")
    if not isinstance(raw, list):
        return []

    history: list[dict[str, str]] = []
    for item in raw[:_MAX_HISTORY_ITEMS]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if len(content) > _MAX_MESSAGE_CONTENT_LENGTH:
            content = content[:_MAX_MESSAGE_CONTENT_LENGTH]
        history.append({"role": role, "content": content})
    return history
