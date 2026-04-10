import asyncio
import hashlib
import json
import re
from collections import OrderedDict
from contextvars import ContextVar
from typing import Any
from uuid import UUID

import jsonschema
from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.tools.tool import Tool, ToolResult
from pydantic import Field, ValidationError
from starlette.responses import JSONResponse

from adapters.observability.logging import get_logger
from domain.mcp_registry.schemas.mcp_registry import McpServerBuildSpec
from domain.tools.schemas.http_result import HttpToolResult
from domain.tools.services.tool_orchestrator import effective_tool_http_url

logger = get_logger(__name__)

_MCP_CONTAINER: ContextVar[object | None] = ContextVar("mcp_container", default=None)

_MCP_PATH_RE = re.compile(
    r"^/core/v1/mcp-servers/([0-9a-fA-F-]{36})/mcp(.*)$",
)

_MCP_APP_CACHE: OrderedDict[tuple, object] = OrderedDict()
_MCP_APP_CACHE_LIMIT = 64
_MCP_LIFESPAN_TASKS: dict[int, asyncio.Task] = {}
_MCP_LIFESPAN_LOCK = asyncio.Lock()


def _header(scope: dict, name: str) -> str | None:
    want = name.lower().encode("latin-1")
    for k, v in scope.get("headers") or []:
        if k.lower() == want:
            return v.decode("latin-1")
    return None


def _spec_cache_key(spec: McpServerBuildSpec) -> tuple:
    ph = tuple(
        (str(pid), hashlib.sha256(c.encode("utf-8")).hexdigest()[:24])
        for pid, _slug, _title, c in spec.prompts
    )
    th = tuple(
        (
            str(b.tool_config_id),
            b.mcp_name,
            hashlib.sha256(
                json.dumps(b.request_schema, sort_keys=True).encode()
            ).hexdigest()[:16],
            hashlib.sha256(
                json.dumps(b.response_schema or {}, sort_keys=True).encode()
            ).hexdigest()[:16],
        )
        for b in spec.tools
    )
    return (
        spec.mcp_server_id,
        th,
        spec.vector_store_ids,
        ph,
        spec.flow_snapshot_id,
        spec.flow_deployment_id,
    )


class _McpHttpProxyTool(Tool):
    KEY_PREFIX = "tool"
    exec_tool_config_id: UUID = Field(exclude=True)
    exec_tenant_id: UUID = Field(exclude=True)

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        tcid = self.exec_tool_config_id
        tenant_id = self.exec_tenant_id
        try:
            vkwargs: dict[str, Any] = {}
            fc = getattr(jsonschema.Draft202012Validator, "FORMAT_CHECKER", None)
            if fc is not None:
                vkwargs["format_checker"] = fc
            jsonschema.validate(instance=arguments, schema=self.parameters, **vkwargs)
        except jsonschema.ValidationError as exc:
            return ToolResult(
                content=json.dumps(
                    {"error": "arguments_validation_failed", "detail": exc.message}
                ),
                structured_content={
                    "error": "arguments_validation_failed",
                    "detail": exc.message,
                },
            )
        ctr = _MCP_CONTAINER.get()
        if ctr is None:
            return ToolResult(
                content=json.dumps({"error": "mcp_context_missing"}),
                structured_content={"error": "mcp_context_missing"},
            )
        tools_repo = ctr.tools.tools_repository()
        cfg_model = await tools_repo.get_tool_config(tcid)
        if cfg_model is None or cfg_model.tenant_id != tenant_id:
            return ToolResult(
                content=json.dumps({"error": "tool_config_not_found"}),
                structured_content={"error": "tool_config_not_found"},
            )
        config: dict = cfg_model.config or {}
        url = effective_tool_http_url(config)
        if not url:
            return ToolResult(
                content=json.dumps({"error": "tool_config_missing_url"}),
                structured_content={"error": "tool_config_missing_url"},
            )
        method = str(config.get("method", "POST"))
        timeout_seconds = float(config.get("timeout_seconds", 10))
        secret_resolver = ctr.adapters.secret_resolver()
        tracer = ctr.adapters.tracer()
        headers: dict[str, str] = {}
        for key, value in (config.get("headers") or {}).items():
            if isinstance(value, dict) and "secret_ref" in value:
                with tracer.observe(
                    as_type="tool",
                    name="adapters.mcp.resolve_tool_secret",
                    input={"secret_ref": str(value["secret_ref"])},
                ):
                    headers[str(key)] = await secret_resolver.resolve(
                        secret_ref=str(value["secret_ref"])
                    )
            elif isinstance(value, str):
                headers[str(key)] = value
            else:
                return ToolResult(
                    content=json.dumps({"error": "invalid_tool_headers_config"}),
                    structured_content={"error": "invalid_tool_headers_config"},
                )
        executor = ctr.execution.tool_executor()
        payload = arguments if isinstance(arguments, dict) else {}
        try:
            result = await executor.execute_http(
                method=method,
                url=str(url),
                headers=headers,
                json_body=payload,
                timeout_seconds=timeout_seconds,
            )
            HttpToolResult.model_validate(result)
        except ValidationError as exc:
            return ToolResult(
                content=json.dumps(
                    {"error": "tool_response_validation_failed", "detail": str(exc)}
                ),
                structured_content={
                    "error": "tool_response_validation_failed",
                    "detail": str(exc),
                },
            )
        except Exception as exc:
            logger.warning(
                "mcp_invoke_tool_failed",
                tool_config_id=str(tcid),
                tenant_id=str(tenant_id),
                error_type=type(exc).__name__,
            )
            return ToolResult(
                content=json.dumps({"error": type(exc).__name__}),
                structured_content={"error": type(exc).__name__},
            )
        out_schema = self.output_schema
        body = result.get("body") if isinstance(result, dict) else None
        if out_schema and isinstance(body, dict):
            try:
                vkwargs2: dict[str, Any] = {}
                fc2 = getattr(jsonschema.Draft202012Validator, "FORMAT_CHECKER", None)
                if fc2 is not None:
                    vkwargs2["format_checker"] = fc2
                jsonschema.validate(instance=body, schema=out_schema, **vkwargs2)
            except jsonschema.ValidationError as exc:
                return ToolResult(
                    content=json.dumps(
                        {
                            "error": "response_body_schema_mismatch",
                            "detail": exc.message,
                        }
                    ),
                    structured_content={
                        "error": "response_body_schema_mismatch",
                        "detail": exc.message,
                    },
                )
            return ToolResult(
                content=json.dumps(body, default=str),
                structured_content=body,
            )
        dumped = HttpToolResult.model_validate(result).model_dump(mode="json")
        return ToolResult(
            content=json.dumps(dumped, default=str),
            structured_content=dumped
            if isinstance(dumped, dict)
            else {"result": dumped},
        )


def _build_http_app_from_spec(spec: McpServerBuildSpec) -> object:
    mcp = FastMCP(f"tenant-mcp-{spec.mcp_server_id}")

    for binding in spec.tools:
        mcp.add_tool(
            _McpHttpProxyTool(
                name=binding.mcp_name,
                description=binding.description or None,
                parameters=binding.request_schema,
                output_schema=binding.response_schema,
                exec_tool_config_id=binding.tool_config_id,
                exec_tenant_id=spec.tenant_id,
            )
        )

    if spec.vector_store_ids:
        vids = tuple(spec.vector_store_ids)
        tid = spec.tenant_id

        def _tenant_id_dep() -> UUID:
            return tid

        def _vector_ids_dep() -> tuple[UUID, ...]:
            return vids

        async def _search_knowledge(
            query: str,
            tenant_id: UUID = Depends(_tenant_id_dep),
            vector_ids: tuple[UUID, ...] = Depends(_vector_ids_dep),
        ) -> str:
            ctr = _MCP_CONTAINER.get()
            if ctr is None:
                return json.dumps({"error": "mcp_context_missing"})
            rag_repo = ctr.rag.rag_repository()
            rag_runtime = ctr.rag.rag_runtime_service()
            all_items: list[dict] = []
            had_published_config = False
            for vid in vector_ids:
                rcid = await rag_repo.get_published_rag_config_id_for_vector_store(
                    tenant_id=tenant_id,
                    vector_store_id=vid,
                )
                if rcid is None:
                    continue
                had_published_config = True
                ctx = await rag_runtime.get_context(
                    tenant_id=tenant_id,
                    rag_config_id=rcid,
                    user_input=query,
                )
                for item in ctx.context_items:
                    all_items.append(
                        {
                            "vector_store_id": str(vid),
                            "content": item.content,
                            "score": item.score,
                        }
                    )
            if vector_ids and not had_published_config:
                return json.dumps({"error": "no_published_rag_config"})
            return json.dumps(all_items, default=str)

        _search_knowledge.__name__ = "search_knowledge"
        mcp.tool(
            name="search_knowledge",
            description="Search tenant knowledge bound to this MCP server.",
        )(_search_knowledge)

    for _pid, slug, title, content in spec.prompts:

        async def _user_prompt(
            *,
            _title: str = title,
            _content: str = content,
        ) -> str:
            return f"{_title}\n\n{_content}"

        _user_prompt.__name__ = re.sub(r"\W+", "_", slug)[:80] or "user_prompt"
        mcp.prompt(name=slug, description=title or slug)(_user_prompt)

    return mcp.http_app(path="/mcp")


def _get_mcp_http_app_for_spec(spec: McpServerBuildSpec) -> object:
    key = _spec_cache_key(spec)
    if key in _MCP_APP_CACHE:
        _MCP_APP_CACHE.move_to_end(key)
        return _MCP_APP_CACHE[key]
    app = _build_http_app_from_spec(spec)
    _MCP_APP_CACHE[key] = app
    while len(_MCP_APP_CACHE) > _MCP_APP_CACHE_LIMIT:
        _MCP_APP_CACHE.popitem(last=False)
    return app


def clear_tenant_mcp_app_cache() -> None:
    _MCP_APP_CACHE.clear()


async def shutdown_tenant_mcp_lifespans() -> None:
    for t in list(_MCP_LIFESPAN_TASKS.values()):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    _MCP_LIFESPAN_TASKS.clear()


async def _ensure_mcp_asgi_lifespan(asgi_app: object) -> None:
    k = id(asgi_app)
    if k in _MCP_LIFESPAN_TASKS:
        return
    async with _MCP_LIFESPAN_LOCK:
        if k in _MCP_LIFESPAN_TASKS:
            return
        ready = asyncio.Event()

        async def _hold_lifespan() -> None:
            async with asgi_app.router.lifespan_context(asgi_app):
                ready.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    pass

        task = asyncio.create_task(_hold_lifespan())
        await ready.wait()
        _MCP_LIFESPAN_TASKS[k] = task


class TenantMcpAsgiMiddleware:
    def __init__(self, app, container: object) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        m = _MCP_PATH_RE.match(path)
        if not m:
            await self.app(scope, receive, send)
            return
        try:
            server_id = UUID(m.group(1))
        except ValueError:
            resp = JSONResponse({"detail": "invalid_mcp_server_id"}, status_code=400)
            await resp(scope, receive, send)
            return
        api_key = _header(scope, "x-api-key")
        if not api_key:
            auth = _header(scope, "authorization") or ""
            if auth.lower().startswith("bearer "):
                api_key = auth[7:].strip()
        if not api_key:
            resp = JSONResponse({"detail": "unauthorized"}, status_code=401)
            await resp(scope, receive, send)
            return
        repo = self.container.mcp_registry.mcp_registry_repository()
        state = await repo.verify_api_key_and_load_bindings(
            mcp_server_id=server_id,
            api_key=api_key,
        )
        if state is None:
            logger.warning(
                "mcp_auth_failed",
                mcp_server_id=str(server_id),
            )
            resp = JSONResponse({"detail": "unauthorized"}, status_code=401)
            await resp(scope, receive, send)
            return
        spec = await repo.fetch_mcp_server_build_spec(state)
        mcp_http = _get_mcp_http_app_for_spec(spec)
        await _ensure_mcp_asgi_lifespan(mcp_http)
        suffix = m.group(2) or ""
        inner_path = "/mcp" + suffix
        new_scope = dict(scope)
        new_scope["path"] = inner_path
        new_scope["raw_path"] = inner_path.encode("utf-8")
        tok_c = _MCP_CONTAINER.set(self.container)
        try:
            await mcp_http(new_scope, receive, send)
        finally:
            _MCP_CONTAINER.reset(tok_c)
