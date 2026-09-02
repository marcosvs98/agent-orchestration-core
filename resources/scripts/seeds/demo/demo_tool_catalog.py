from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname
from uuid import UUID, uuid5

import httpx

from domain.tools.schemas.openapi_types import OpenAPISpec
from domain.tools.services.openapi_parser import OpenAPIParser

_NS = UUID("c9f8e0a1-2b3c-4d5e-6f70-1a2b3c4d5e6f")

DEFAULT_DEMO_API_HTTP_BASE = "http://demo-api:8088"
DEFAULT_DEMO_TOOL_OPERATION_ID = "create_expense"

_MUTATING_AND_READ_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _looks_loopback(url: str) -> bool:
    candidate = (url or "").strip().lower().rstrip("/")
    if not candidate:
        return True
    for prefix in ("https://", "http://"):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix) :]
            break
    host = candidate.split("/", 1)[0].split(":", 1)[0]
    return host in {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


def resolve_demo_api_execution_base(*, openapi_server_url: str | None = None) -> str:
    explicit = os.getenv("DEMO_API_HTTP_BASE", "").strip().rstrip("/")
    if explicit:
        return explicit
    advertised = (openapi_server_url or "").strip().rstrip("/")
    if advertised and not _looks_loopback(advertised):
        return advertised
    return DEFAULT_DEMO_API_HTTP_BASE


def _fixture_spec_path() -> Path:
    return Path(__file__).resolve().parent / "openapi" / "demo_api.json"


def resolve_openapi_source(openapi_url: str | None = None) -> str:
    explicit = openapi_url or os.getenv("DEMO_OPENAPI_URL", "").strip()
    if explicit:
        return explicit
    return str(_fixture_spec_path())


async def _read_openapi_document(source: str) -> dict[str, Any]:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(source)
            response.raise_for_status()
            return response.json()

    path = Path(url2pathname(parsed.path)) if parsed.scheme == "file" else Path(source)
    if not path.is_file():
        raise RuntimeError(f"openapi document not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


async def fetch_demo_tool_rows(
    *,
    openapi_url: str | None = None,
    demo_tool_id: UUID | None = None,
    demo_tool_config_id: UUID | None = None,
    demo_operation_id: str | None = None,
) -> list[dict[str, Any]]:
    url = resolve_openapi_source(openapi_url)
    spec_dict = await _read_openapi_document(url)

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
    if isinstance(servers, list) and servers:
        openapi_base = str(servers[0].get("url", "") or "").strip().rstrip("/")

    exec_base = resolve_demo_api_execution_base(openapi_server_url=openapi_base or None)
    demo_op = demo_operation_id or os.getenv(
        "DEMO_TOOL_OPERATION_ID", DEFAULT_DEMO_TOOL_OPERATION_ID
    )

    rows: list[dict[str, Any]] = []
    for op in operations:
        oid = str(op["operation_id"])
        if str(op["method"]).upper() not in _MUTATING_AND_READ_METHODS:
            continue
        if demo_tool_id is not None and demo_tool_config_id is not None and oid == demo_op:
            tid, tcid = demo_tool_id, demo_tool_config_id
        else:
            tid, tcid = uuid5(_NS, f"tool:{oid}"), uuid5(_NS, f"tcfg:{oid}")
        request_schema = op.get("request_schema")
        response_schema = op.get("response_schema")
        examples = op.get("examples")
        rows.append(
            {
                "operation_id": oid,
                "tool_name": oid,
                "tool_id": tid,
                "tool_config_id": tcid,
                "path": str(op["path"]),
                "method": str(op["method"]),
                "summary": op.get("summary"),
                "description": op.get("description"),
                "request_schema": request_schema if isinstance(request_schema, dict) else {},
                "response_schema": response_schema if isinstance(response_schema, dict) else {},
                "examples": examples if isinstance(examples, list) else [],
                "execution_base_url": exec_base,
            }
        )
    rows.sort(key=lambda row: str(row["operation_id"]))
    if not rows:
        raise RuntimeError(f"no operations found in the OpenAPI document at {url}")
    return rows
