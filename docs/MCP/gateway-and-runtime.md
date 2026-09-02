# Gateway and runtime

MCP **session handling** and **tool execution** are implemented in **`src/adapters/mcp/tenant_mcp_gateway.py`**. The domain registry decides **which** tools and resources belong to a server; this module builds a **FastMCP** ASGI application per **`McpServerBuildSpec`** and executes HTTP-backed tools through the same **`tool_executor`** stack as graph execution.

## Request routing and auth

### URL pattern

Requests must match:

`^/core/v1/mcp-servers/([uuid])/mcp(.*)$`

The middleware extracts **`mcp_server_id`**, then rewrites the inner path to **`/mcp` + suffix** for the FastMCP app (`inner_path`).

### API key

The gateway accepts:

- Header **`X-Api-Key`**, or
- **`Authorization: Bearer <token>`**

If missing or invalid → **401** JSON `{"detail": "unauthorized"}`.

```mermaid
sequenceDiagram
  participant MC as MCP client
  participant MW as TenantMcpAsgiMiddleware
  participant Repo as McpRegistryRepository
  participant App as FastMCP http_app
  MC->>MW: HTTP /core/v1/mcp-servers/{id}/mcp/...
  MW->>MW: Regex match + parse UUID
  MW->>MW: Read X-Api-Key or Bearer
  MW->>Repo: verify_api_key_and_load_bindings
  alt Invalid key / server
    Repo-->>MW: None
    MW-->>MC: 401 unauthorized
  else OK
    Repo-->>MW: McpBindingState
    MW->>Repo: fetch_mcp_server_build_spec(state)
    Repo-->>MW: McpServerBuildSpec
    MW->>App: get cached FastMCP app for spec
    MW->>MW: _MCP_CONTAINER.set(container)
    MW->>MW: _MCP_INBOUND_INTERACTION_METADATA.set(inbound)
    App-->>MC: MCP protocol response
    MW->>MW: reset context vars
  end
```

When **`X-Api-Key`** is present and **`Authorization: Bearer …`** is a **different** string than the API key value, the middleware records **`end_user_authorization`** (full `Authorization` header value) for HTTP tools whose `tool_config` maps **`Authorization`** via **`interaction_metadata_key`** (same contract as **`ToolOrchestrator._resolve_headers`**). FastMCP may run tool handlers outside that ASGI `ContextVar` visibility; **`_mcp_interaction_metadata_for_http_tools`** therefore also reads the inbound **`Authorization`** from **`get_http_request()`** when the context var has no end-user token yet.

### Outbound authorization fallback

An MCP client is not always able to present an end-user token. When the server has an
**`outbound_authorization_secret_ref`** (set at creation or via
[`PATCH .../outbound-authorization`](registry-and-api.md#patch-outbound-authorization)), the
middleware puts it on the context var **`_MCP_OUTBOUND_AUTH_SECRET_REF`** for the duration of the
request, and `_McpHttpProxyTool.run` uses it **only as a fallback**:

1. Read the current `end_user_authorization` from interaction metadata (inbound header first, then
   the `get_http_request()` fallback).
2. **If that value is present and non-empty, the secret ref is ignored.** A caller-supplied
   end-user token always wins.
3. Otherwise resolve the ref through **`SecretResolverPort`** under the span
   `adapters.mcp.resolve_mcp_outbound_auth_fallback`, and — if the resolved value does not already
   start with `bearer ` — prefix it with `Bearer `.
4. Write the result into the metadata map that `interaction_metadata_key` headers read from, so a
   tool config binding `Authorization` → `end_user_authorization` resolves normally.

A failed resolution is swallowed (`resolved = ""`), which leaves the metadata key absent and makes
the tool call fail with `interaction_metadata_header_missing` rather than calling the upstream
unauthenticated.

!!! warning "This is a tenant-wide credential"

    The fallback applies to **every** call through that MCP server that did not carry an end-user
    token, so outbound requests stop being attributable to an individual end user. Use it for
    service-to-service integrations, not as a convenience for user-facing clients that could send
    their own token.

The secret ref participates in **`_spec_cache_key`**, so changing it rebuilds the cached FastMCP app
rather than serving the previous credential.

### Application container context

`_McpHttpProxyTool.run` and **`search_knowledge`** read **`ApplicationContainer`** from the context var **`_MCP_CONTAINER`**. If it is not set (middleware bug or direct invocation), tools return structured errors such as **`mcp_context_missing`**.

## Building the FastMCP app: `_build_http_app_from_spec`

For each **`McpServerToolBinding`**, the gateway registers **`_McpHttpProxyTool`**:

- **Tool name** = `binding.mcp_name`
- **`parameters`** = `request_schema` (JSON Schema for MCP arguments)
- Optional **`output_schema`** for response body validation

### Tool call path: `_McpHttpProxyTool.run`

On **`run(arguments)`**:

1. **Validate** `arguments` with **jsonschema** against `parameters` → on failure, return `arguments_validation_failed`.
2. Resolve container; load **`tool_config`** by `exec_tool_config_id`; enforce **`tenant_id`** matches `exec_tenant_id`.
3. Resolve HTTP **`url`** via `effective_tool_http_url(config)`, **method** (default `POST`), **`timeout_seconds`** (default `10`).
4. Resolve **headers**: plain strings, **`secret_ref`** via **`SecretResolverPort`**, or **`interaction_metadata_key`** resolved from **`_mcp_interaction_metadata_for_http_tools()`** (middleware context var plus **`get_http_request()`** fallback), after applying the [outbound authorization fallback](#outbound-authorization-fallback).
5. Call **`tool_executor.execute_http`** with JSON body = MCP arguments (dict).
6. Validate **`HttpToolResult`**; if `response_schema` is set and body is a dict, **jsonschema**-validate body; otherwise return a structured dump of the HTTP result.

```mermaid
flowchart TD
  A[MCP tool invoke] --> B[jsonschema validate arguments]
  B --> C[Load tool_config by id + tenant]
  C --> D[effective_tool_http_url + method + timeout]
  D --> E[Resolve headers + secrets]
  E --> F[tool_executor.execute_http]
  F --> G{response_schema + dict body?}
  G -->|yes| H[Validate body + return ToolResult]
  G -->|no| I[HttpToolResult dump as ToolResult]
```

So: **MCP clients see named tools**; the adapter **maps** each name to a persisted **HTTP tool config** and performs the outbound request.

### Error surfaces (non-exhaustive)

| Condition | Typical structured error |
|-----------|---------------------------|
| Invalid arguments | `arguments_validation_failed` |
| Missing container | `mcp_context_missing` |
| Wrong tenant / missing config | `tool_config_not_found` |
| No URL in config | `tool_config_missing_url` |
| Bad header shape | `invalid_tool_headers_config` |
| Missing interaction metadata for a header | `interaction_metadata_header_missing` |
| HTTP/validation failure | `tool_response_validation_failed` or exception type name |
| Body vs schema | `response_body_schema_mismatch` |

## Optional tool: `search_knowledge`

If **`spec.vector_store_ids`** is non-empty, the gateway registers **`search_knowledge`**:

- For each bound vector store, resolves a **published RAG config** id.
- Calls **`RagRuntimeService.get_context`** per store, aggregates scored chunks.
- If vector ids were given but **no** published config existed → JSON `{"error": "no_published_rag_config"}`.

```mermaid
flowchart LR
  Q[query string] --> SK[search_knowledge]
  SK --> RAG[RagRuntimeService.get_context]
  RAG --> J[JSON list of chunks + scores]
```

See [RAG runtime and integration](../RAG/runtime-and-integration.md).

## Prompts

For each bound user prompt, **`mcp.prompt(name=slug, ...)`** registers a template that returns **`title` + `content`** as plain text (implementation concatenates with a newline).

## Caching and lifespan

- **`_spec_cache_key`** — hashes tool bindings (ids, `mcp_name`, request/response schema fingerprints), vector ids, prompt content hashes, and flow ids.
- **`_MCP_APP_CACHE`** — LRU of built ASGI apps (limit **64**).
- **`_ensure_mcp_asgi_lifespan`** — holds the FastMCP app’s lifespan context in a background task so the app stays initialized under load.

Use **`clear_tenant_mcp_app_cache()`** / **`shutdown_tenant_mcp_lifespans()`** in tests or controlled shutdown (see module docstrings and call sites).

OpenAPI **import-tools** (`ToolsService.import_tool`) sets **`config.base_url`** with **`resolve_tool_import_base_url`** (OpenAPI `servers`, else origin of the fetch URL, else **`TOOL_IMPORT_DEFAULT_BASE_URL`**) and merges a default **`Authorization` → `end_user_authorization`** header for outbound calls. See **`src/domain/tools/services/tool_import_http_base.py`**.

## Related

- [Registry and API](registry-and-api.md)
- [RAG runtime and integration](../RAG/runtime-and-integration.md)
