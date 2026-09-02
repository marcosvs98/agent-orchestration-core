from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from domain.common.interaction_metadata import END_USER_AUTHORIZATION_METADATA_KEY

DEFAULT_IMPORT_TOOL_HEADERS: dict[str, dict[str, str]] = {
    "Authorization": {"interaction_metadata_key": END_USER_AUTHORIZATION_METADATA_KEY},
}


def resolve_tool_import_base_url(
    *,
    openapi_servers: list[Any] | None,
    openapi_fetch_url: str,
    default_base_url: str = "",
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
    return default_base_url.strip().rstrip("/")
