from __future__ import annotations

from typing import Any


def parse_message_history(metadata: dict[str, object] | None) -> list[dict[str, str]]:
    if not metadata:
        return []
    raw = metadata.get("message_history")
    if not isinstance(raw, list):
        return []

    history: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        history.append({"role": role, "content": content})
    return history
