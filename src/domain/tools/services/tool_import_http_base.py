from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

DEFAULT_UORA_IMPORT_TOOL_HEADERS: dict[str, dict[str, str]] = {
    "Authorization": {"interaction_metadata_key": "uora_end_user_authorization"},
}


def resolve_tool_import_base_url(
    *,
    openapi_servers: list[Any] | None,
    openapi_fetch_url: str,
) -> str:
    raw = ""
    servers = openapi_servers if isinstance(openapi_servers, list) else []
    if servers and isinstance(servers[0], dict):
        raw = str(servers[0].get("url") or "").strip()
    cand = raw.rstrip("/")
    if cand.startswith("http://") or cand.startswith("https://"):
        parts = urlparse(cand)
        if parts.scheme and parts.netloc:
            if parts.path in ("", "/"):
                return f"{parts.scheme}://{parts.netloc}".rstrip("/")
            return cand
    fetch = urlparse(openapi_fetch_url)
    if fetch.scheme in ("http", "https") and fetch.netloc:
        return f"{fetch.scheme}://{fetch.netloc}".rstrip("/")
    env = os.environ.get("UORA_APP_PLATFORM_HTTP_BASE", "").strip().rstrip("/")
    if env:
        return env
    return "http://host.docker.internal:8088"
