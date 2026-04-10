from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import httpx

from domain.tools.schemas.openapi_types import OpenAPISpec
from domain.tools.services.openapi_parser import OpenAPIParser

_NS = UUID("c9f8e0a1-2b3c-4d5e-6f70-1a2b3c4d5e6f")

# Default when OpenAPI advertises loopback (common in local specs) — safe for AOC running in Docker.
# For seeds executed on the host against app-platform on localhost, set:
#   UORA_APP_PLATFORM_HTTP_BASE=http://127.0.0.1:8088
DEFAULT_UORA_APP_PLATFORM_HTTP_BASE = "http://host.docker.internal:8088"


def _openapi_server_looks_loopback(url: str) -> bool:
    u = (url or "").strip().lower().rstrip("/")
    if not u:
        return True
    # Strip scheme for host checks
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix) :]
            break
    host = u.split("/", 1)[0].split(":", 1)[0]
    return host in {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


def resolve_uora_app_platform_execution_base(*, openapi_server_url: str | None = None) -> str:
    """Base URL used in tool_config.base_url and for building tool_config.url (path appended).

    Order:
    1. ``UORA_APP_PLATFORM_HTTP_BASE`` when non-empty.
    2. First OpenAPI ``servers[0].url`` when present and **not** loopback (e.g. deployed spec).
    3. :data:`DEFAULT_UORA_APP_PLATFORM_HTTP_BASE` (Docker → host gateway).

    OpenAPI loopback URLs are **not** reused for execution: specs often say ``http://127.0.0.1:8088``,
    which breaks HTTP tool calls from inside a container even when the spec was fetched correctly.
    """
    explicit = os.getenv("UORA_APP_PLATFORM_HTTP_BASE", "").strip().rstrip("/")
    if explicit:
        return explicit
    oa = (openapi_server_url or "").strip().rstrip("/")
    if oa and not _openapi_server_looks_loopback(oa):
        return oa
    return DEFAULT_UORA_APP_PLATFORM_HTTP_BASE


def _allowlist_path() -> Path:
    return Path(__file__).resolve().parents[4] / "resources" / "config" / "uora_finance_tool_allowlist.json"


def _load_allowlist() -> tuple[set[str], dict[str, str]]:
    raw = json.loads(_allowlist_path().read_text(encoding="utf-8"))
    ids = raw.get("operation_ids") or []
    allowed = {str(x) for x in ids} if isinstance(ids, list) else set()
    names = raw.get("tool_names") or {}
    name_map: dict[str, str] = {}
    if isinstance(names, dict):
        for k, v in names.items():
            name_map[str(k)] = str(v)
    return allowed, name_map


async def fetch_uora_platform_tool_rows(
    *,
    openapi_url: str | None = None,
    demo_tool_id: UUID | None = None,
    demo_tool_config_id: UUID | None = None,
    demo_operation_id: str | None = None,
) -> list[dict[str, Any]]:
    url = openapi_url or os.getenv(
        "UORA_OPENAPI_URL", "http://127.0.0.1:8088/openapi.json"
    )
    allowed, name_map = _load_allowlist()
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        spec_dict = response.json()

    parser = OpenAPIParser()
    parsed = OpenAPISpec(
        title=spec_dict.get("info", {}).get("title", "API"),
        version=spec_dict.get("info", {}).get("version", "1.0.0"),
        paths=spec_dict.get("paths", {}),
        schemas=spec_dict.get("components", {}).get("schemas", {}),
        openapi_version=spec_dict.get("openapi"),
        servers=spec_dict.get("servers", []),
        components=spec_dict.get("components", {}),
    )
    operations = parser.extract_operations(parsed)
    servers = parsed.get("servers") or []
    openapi_base = ""
    if servers and isinstance(servers, list) and len(servers) > 0:
        openapi_base = str(servers[0].get("url", "") or "").strip().rstrip("/")

    exec_base = resolve_uora_app_platform_execution_base(
        openapi_server_url=openapi_base or None,
    )

    demo_op = demo_operation_id or os.getenv(
        "UORA_DEMO_TOOL_OPERATION_ID", "spending_by_category"
    )

    rows: list[dict[str, Any]] = []
    for op in operations:
        oid = op["operation_id"]
        if oid not in allowed:
            continue
        # Allow GET and mutating verbs when explicitly allowlisted (e.g. POST manual transaction).
        method_upper = str(op["method"]).upper()
        if method_upper not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            continue
        if demo_tool_id is not None and demo_tool_config_id is not None and oid == demo_op:
            tid, tcid = demo_tool_id, demo_tool_config_id
        else:
            tid, tcid = uuid5(_NS, f"tool:{oid}"), uuid5(_NS, f"tcfg:{oid}")
        rs = op.get("request_schema")
        if not isinstance(rs, dict):
            rs = {}
        rps = op.get("response_schema")
        if not isinstance(rps, dict):
            rps = {}
        ex = op.get("examples")
        if not isinstance(ex, list):
            ex = []
        tool_name = name_map.get(oid, oid)
        rows.append({
            "operation_id": oid,
            "tool_name": tool_name,
            "tool_id": tid,
            "tool_config_id": tcid,
            "path": str(op["path"]),
            "method": str(op["method"]),
            "summary": op.get("summary"),
            "description": op.get("description"),
            "request_schema": rs,
            "response_schema": rps,
            "examples": ex,
            "execution_base_url": exec_base,
        })
    rows.sort(key=lambda r: str(r["operation_id"]))
    if not rows:
        raise RuntimeError(
            f"no allowlisted operations in OpenAPI at {url}"
        )
    return rows
