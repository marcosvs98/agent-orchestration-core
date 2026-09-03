import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

import adapters.mcp.tenant_mcp_gateway as tenant_mcp_gateway_mod
from app import create_app
from domain.mcp_registry.schemas.mcp_registry import (
    McpBindingState,
    McpServerBuildSpec,
    McpServerToolBinding,
)
from domain.rag.schemas.rag import RagContext, RagContextItem, RagContextReason


def _sse_json_payloads(text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.split("\n"):
        if line.startswith("data:"):
            out.append(json.loads(line[5:].strip()))
    return out


def _mcp_json_rpc_result(response: object) -> dict:
    ct = (response.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        return response.json()
    payloads = _sse_json_payloads(response.text)
    assert payloads
    return payloads[-1]


def _mcp_accept() -> str:
    return "application/json"


@pytest.fixture(autouse=True)
def _reset_mcp_cache_after_test() -> object:
    yield
    tenant_mcp_gateway_mod.clear_tenant_mcp_app_cache()
    try:
        asyncio.run(tenant_mcp_gateway_mod.shutdown_tenant_mcp_lifespans())
    except RuntimeError:
        pass


@pytest.fixture
def mcp_server_id() -> object:
    return uuid4()


@pytest.fixture
def tenant_id() -> object:
    return uuid4()


def _repo_with_spec(
    mcp_server_id: object,
    tenant_id: object,
    spec: McpServerBuildSpec,
) -> MagicMock:
    repo = MagicMock()
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset(),
            vector_store_ids=frozenset(),
            user_prompt_ids=frozenset(),
        )
    )
    repo.fetch_mcp_server_build_spec = AsyncMock(return_value=spec)
    return repo


@pytest.fixture
def mock_mcp_repo(mcp_server_id, tenant_id) -> MagicMock:
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=tuple(),
        vector_store_ids=tuple(),
        prompts=tuple(),
    )
    return _repo_with_spec(mcp_server_id, tenant_id, spec)


@pytest.fixture
def client_with_mcp(mock_mcp_repo) -> object:
    app = create_app()
    app.state.container.mcp_registry.mcp_registry_repository.override(
        providers.Object(mock_mcp_repo)
    )
    with TestClient(app) as client:
        yield client, mock_mcp_repo


def test_mcp_post_without_api_key_returns_401(client_with_mcp, mcp_server_id) -> None:
    client, _ = client_with_mcp
    r = client.post(
        f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
        json={"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1},
        headers={"Accept": _mcp_accept(), "Content-Type": "application/json"},
    )
    assert r.status_code == 401


def test_mcp_tools_list_empty_when_no_bindings(client_with_mcp, mcp_server_id) -> None:
    client, _ = client_with_mcp
    r1 = client.post(
        f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1"},
            },
            "id": 1,
        },
        headers={
            "X-Api-Key": "k",
            "Accept": _mcp_accept(),
            "Content-Type": "application/json",
        },
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
        json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
        headers={
            "X-Api-Key": "k",
            "Accept": _mcp_accept(),
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2024-11-05",
        },
    )
    assert r2.status_code == 200
    body = _mcp_json_rpc_result(r2)
    tools = body["result"]["tools"]
    assert tools == []


def test_mcp_named_tool_invoke(mcp_server_id, tenant_id) -> None:
    tcid = uuid4()
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=(
            McpServerToolBinding(
                tool_config_id=tcid,
                mcp_name="createExpense",
                description="Creates expense",
                request_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
                response_schema=None,
            ),
        ),
        vector_store_ids=tuple(),
        prompts=tuple(),
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset([tcid]),
            vector_store_ids=frozenset(),
            user_prompt_ids=frozenset(),
        )
    )
    cfg = MagicMock()
    cfg.tenant_id = tenant_id
    cfg.config = {"url": "https://example.com", "method": "GET", "timeout_seconds": 5}
    tools_repo = MagicMock()
    tools_repo.get_tool_config = AsyncMock(return_value=cfg)
    mock_exec = MagicMock()
    mock_exec.execute_http = AsyncMock(
        return_value={"status_code": 200, "headers": {}, "body": {"x": 1}}
    )
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    ctr.tools.tools_repository.override(providers.Factory(lambda: tools_repo))
    ctr.execution.tool_executor.override(providers.Object(mock_exec))
    with TestClient(app) as client:
        client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
            },
        )
        r_list = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
        listed = _mcp_json_rpc_result(r_list)["result"]["tools"]
        names = [t["name"] for t in listed]
        assert names == ["createExpense"]
        props = listed[0]["inputSchema"].get("properties") or {}
        assert "arguments" not in props
        assert "_tcid" not in props
        assert "_tenant_id" not in props
        r2 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "createExpense",
                    "arguments": {},
                },
                "id": 3,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
    out = _mcp_json_rpc_result(r2)
    assert out["result"]["isError"] is False
    mock_exec.execute_http.assert_awaited()
    call_kw = mock_exec.execute_http.await_args.kwargs
    assert call_kw["json_body"] == {}


def test_mcp_named_tool_invoke_resolves_interaction_metadata_authorization(
    mcp_server_id, tenant_id
) -> None:
    tcid = uuid4()
    user_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.e30"
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=(
            McpServerToolBinding(
                tool_config_id=tcid,
                mcp_name="spendingByCategory",
                description="Spending",
                request_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
                response_schema=None,
            ),
        ),
        vector_store_ids=tuple(),
        prompts=tuple(),
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset([tcid]),
            vector_store_ids=frozenset(),
            user_prompt_ids=frozenset(),
        )
    )
    cfg = MagicMock()
    cfg.tenant_id = tenant_id
    cfg.config = {
        "url": "https://example.com/api",
        "method": "GET",
        "timeout_seconds": 5,
        "headers": {
            "Authorization": {
                "interaction_metadata_key": "end_user_authorization",
            },
        },
    }
    tools_repo = MagicMock()
    tools_repo.get_tool_config = AsyncMock(return_value=cfg)
    mock_exec = MagicMock()
    mock_exec.execute_http = AsyncMock(
        return_value={"status_code": 200, "headers": {}, "body": {"ok": True}}
    )
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    ctr.tools.tools_repository.override(providers.Factory(lambda: tools_repo))
    ctr.execution.tool_executor.override(providers.Object(mock_exec))
    hdr = {"Authorization": f"Bearer {user_jwt}"}
    with TestClient(app) as client:
        r1 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "mcp-integration-key",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                **hdr,
            },
        )
        assert r1.status_code == 200
        r_list = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            headers={
                "X-Api-Key": "mcp-integration-key",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
                **hdr,
            },
        )
        assert r_list.status_code == 200
        r2 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "spendingByCategory",
                    "arguments": {},
                },
                "id": 3,
            },
            headers={
                "X-Api-Key": "mcp-integration-key",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
                **hdr,
            },
        )
    out = _mcp_json_rpc_result(r2)
    assert out["result"]["isError"] is False
    call_kw = mock_exec.execute_http.await_args.kwargs
    assert call_kw["headers"]["Authorization"] == f"Bearer {user_jwt}"


def test_mcp_named_tool_invoke_outbound_authorization_env_fallback(
    mcp_server_id, tenant_id
) -> None:
    tcid = uuid4()
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=(
            McpServerToolBinding(
                tool_config_id=tcid,
                mcp_name="spendingByCategory",
                description="Spending",
                request_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
                response_schema=None,
            ),
        ),
        vector_store_ids=tuple(),
        prompts=tuple(),
        outbound_authorization_secret_ref="env:MCP_FALLBACK_JWT",
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset([tcid]),
            vector_store_ids=frozenset(),
            user_prompt_ids=frozenset(),
        )
    )
    cfg = MagicMock()
    cfg.tenant_id = tenant_id
    cfg.config = {
        "url": "https://example.com/api",
        "method": "GET",
        "timeout_seconds": 5,
        "headers": {
            "Authorization": {
                "interaction_metadata_key": "end_user_authorization",
            },
        },
    }
    tools_repo = MagicMock()
    tools_repo.get_tool_config = AsyncMock(return_value=cfg)
    mock_exec = MagicMock()
    mock_exec.execute_http = AsyncMock(
        return_value={"status_code": 200, "headers": {}, "body": {"ok": True}}
    )
    mock_secret = MagicMock()
    mock_secret.resolve = AsyncMock(return_value="fallback-raw-token")
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    ctr.tools.tools_repository.override(providers.Factory(lambda: tools_repo))
    ctr.execution.tool_executor.override(providers.Object(mock_exec))
    ctr.adapters.secret_resolver.override(providers.Object(mock_secret))
    with TestClient(app) as client:
        r1 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "mcp-integration-key",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
            },
        )
        assert r1.status_code == 200
        r_list = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            headers={
                "X-Api-Key": "mcp-integration-key",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
        assert r_list.status_code == 200
        r2 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "spendingByCategory",
                    "arguments": {},
                },
                "id": 3,
            },
            headers={
                "X-Api-Key": "mcp-integration-key",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
    out = _mcp_json_rpc_result(r2)
    assert out["result"]["isError"] is False
    mock_secret.resolve.assert_awaited()
    call_kw = mock_exec.execute_http.await_args.kwargs
    assert call_kw["headers"]["Authorization"] == "Bearer fallback-raw-token"


def test_mcp_tool_input_schema_from_binding(mcp_server_id, tenant_id) -> None:
    tcid = uuid4()
    req = {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "currency": {"type": "string"},
        },
        "required": ["amount", "currency"],
    }
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=(
            McpServerToolBinding(
                tool_config_id=tcid,
                mcp_name="createExpense",
                description="Creates expense",
                request_schema=req,
                response_schema=None,
            ),
        ),
        vector_store_ids=tuple(),
        prompts=tuple(),
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset([tcid]),
            vector_store_ids=frozenset(),
            user_prompt_ids=frozenset(),
        )
    )
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    with TestClient(app) as client:
        client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
            },
        )
        r_list = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
    tool = _mcp_json_rpc_result(r_list)["result"]["tools"][0]
    assert tool["inputSchema"]["properties"]["amount"]["type"] == "number"
    assert tool["inputSchema"]["properties"]["currency"]["type"] == "string"
    assert "amount" in tool["inputSchema"]["required"]


def test_mcp_search_knowledge_query_only(mcp_server_id, tenant_id) -> None:
    vid = uuid4()
    rcid = uuid4()
    doc_id = uuid4()
    chunk_id = uuid4()
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=tuple(),
        vector_store_ids=(vid,),
        prompts=tuple(),
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset(),
            vector_store_ids=frozenset([vid]),
            user_prompt_ids=frozenset(),
        )
    )
    rag_repo = MagicMock()
    rag_repo.get_published_rag_config_id_for_vector_store = AsyncMock(return_value=rcid)
    rag_rt = MagicMock()
    rag_rt.get_context = AsyncMock(
        return_value=RagContext(
            context_items=[
                RagContextItem(
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    content="chunk text",
                    score=0.91,
                )
            ],
            eligible=True,
            reason=RagContextReason.OK,
        )
    )
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    ctr.rag.rag_repository.override(providers.Factory(lambda: rag_repo))
    ctr.rag.rag_runtime_service.override(providers.Factory(lambda: rag_rt))
    with TestClient(app) as client:
        client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
            },
        )
        r2 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "search_knowledge",
                    "arguments": {
                        "query": "q",
                    },
                },
                "id": 4,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
    out = _mcp_json_rpc_result(r2)
    text = out["result"]["content"][0]["text"]
    data = json.loads(text)
    assert len(data) == 1
    assert data[0]["content"] == "chunk text"
    assert data[0]["vector_store_id"] == str(vid)
    rag_rt.get_context.assert_awaited_once()
    call_kwargs = rag_rt.get_context.await_args.kwargs
    assert call_kwargs["tenant_id"] == tenant_id
    assert call_kwargs["rag_config_id"] == rcid
    assert "user_id" not in call_kwargs
    assert call_kwargs["user_input"] == "q"


def test_mcp_search_knowledge_no_published_rag_config(mcp_server_id, tenant_id) -> None:
    vid = uuid4()
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=tuple(),
        vector_store_ids=(vid,),
        prompts=tuple(),
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset(),
            vector_store_ids=frozenset([vid]),
            user_prompt_ids=frozenset(),
        )
    )
    rag_repo = MagicMock()
    rag_repo.get_published_rag_config_id_for_vector_store = AsyncMock(return_value=None)
    rag_rt = MagicMock()
    rag_rt.get_context = AsyncMock()
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    ctr.rag.rag_repository.override(providers.Factory(lambda: rag_repo))
    ctr.rag.rag_runtime_service.override(providers.Factory(lambda: rag_rt))
    with TestClient(app) as client:
        client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
            },
        )
        r2 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "search_knowledge",
                    "arguments": {"query": "q"},
                },
                "id": 4,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
    out = _mcp_json_rpc_result(r2)
    text = out["result"]["content"][0]["text"]
    assert json.loads(text) == {"error": "no_published_rag_config"}
    rag_rt.get_context.assert_not_awaited()


def test_mcp_search_knowledge_empty_list_when_config_but_no_chunks(
    mcp_server_id,
    tenant_id,
) -> None:
    vid = uuid4()
    rcid = uuid4()
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=tuple(),
        vector_store_ids=(vid,),
        prompts=tuple(),
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset(),
            vector_store_ids=frozenset([vid]),
            user_prompt_ids=frozenset(),
        )
    )
    rag_repo = MagicMock()
    rag_repo.get_published_rag_config_id_for_vector_store = AsyncMock(return_value=rcid)
    rag_rt = MagicMock()
    rag_rt.get_context = AsyncMock(
        return_value=RagContext(
            context_items=[],
            eligible=False,
            reason=RagContextReason.NO_MATCHES,
        )
    )
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    ctr.rag.rag_repository.override(providers.Factory(lambda: rag_repo))
    ctr.rag.rag_runtime_service.override(providers.Factory(lambda: rag_rt))
    with TestClient(app) as client:
        client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
            },
        )
        r2 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "search_knowledge",
                    "arguments": {"query": "q"},
                },
                "id": 4,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
    out = _mcp_json_rpc_result(r2)
    text = out["result"]["content"][0]["text"]
    assert json.loads(text) == []
    rag_rt.get_context.assert_awaited_once()


def test_mcp_prompts_list(mcp_server_id, tenant_id) -> None:
    pid = uuid4()
    spec = McpServerBuildSpec(
        tenant_id=tenant_id,
        mcp_server_id=mcp_server_id,
        tools=tuple(),
        vector_store_ids=tuple(),
        prompts=((pid, "demo_title_abcdef01", "Demo Title", "Prompt body here"),),
    )
    repo = _repo_with_spec(mcp_server_id, tenant_id, spec)
    repo.verify_api_key_and_load_bindings = AsyncMock(
        return_value=McpBindingState(
            tenant_id=tenant_id,
            mcp_server_id=mcp_server_id,
            tool_config_ids=frozenset(),
            vector_store_ids=frozenset(),
            user_prompt_ids=frozenset([pid]),
        )
    )
    app = create_app()
    ctr = app.state.container
    ctr.mcp_registry.mcp_registry_repository.override(providers.Object(repo))
    with TestClient(app) as client:
        client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
                "id": 1,
            },
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
            },
        )
        r2 = client.post(
            f"/core/v1/mcp-servers/{mcp_server_id}/mcp",
            json={"jsonrpc": "2.0", "method": "prompts/list", "id": 2},
            headers={
                "X-Api-Key": "k",
                "Accept": _mcp_accept(),
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
            },
        )
    plist = _mcp_json_rpc_result(r2)["result"]["prompts"]
    assert len(plist) == 1
    assert plist[0]["name"] == "demo_title_abcdef01"


@pytest.mark.asyncio
async def test_mcp_http_proxy_tool_logs_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from adapters.mcp import tenant_mcp_gateway as gateway_mod
    from adapters.mcp.tenant_mcp_gateway import _McpHttpProxyTool

    tenant_id = uuid4()
    tool_config_id = uuid4()
    captured: list[dict] = []

    class _FakeLogger:
        def warning(self, event: str, **kwargs) -> None:
            captured.append({"event": event, **kwargs})

    monkeypatch.setattr(gateway_mod, "logger", _FakeLogger())

    cfg_model = MagicMock()
    cfg_model.tenant_id = tenant_id
    cfg_model.config = {
        "url": "http://host.docker.internal:8088/core/v1/foo?token=secret",
        "method": "GET",
        "operation_id": "getFoo",
        "timeout_seconds": 5,
    }

    tools_repo = MagicMock()
    tools_repo.get_tool_config = AsyncMock(return_value=cfg_model)

    mock_exec = MagicMock()
    mock_exec.execute_http = AsyncMock(
        side_effect=httpx.ConnectError(
            "[Errno -2] Name or service not known",
            request=httpx.Request("GET", cfg_model.config["url"]),
        )
    )

    ctr = MagicMock()
    ctr.tools.tools_repository.return_value = tools_repo
    ctr.execution.tool_executor.return_value = mock_exec
    ctr.adapters.secret_resolver.return_value = MagicMock()
    ctr.adapters.tracer.return_value = MagicMock()

    tok = gateway_mod._MCP_CONTAINER.set(ctr)
    try:
        tool = _McpHttpProxyTool(
            name="getFoo",
            description=None,
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            output_schema=None,
            exec_tool_config_id=tool_config_id,
            exec_tenant_id=tenant_id,
        )
        result = await tool.run({})
    finally:
        gateway_mod._MCP_CONTAINER.reset(tok)

    assert result.structured_content == {"error": "ConnectError"}
    assert captured
    log_entry = captured[0]
    assert log_entry["event"] == "mcp_invoke_tool_failed"
    assert log_entry["tool_config_id"] == str(tool_config_id)
    assert log_entry["operation_id"] == "getFoo"
    assert log_entry["method"] == "GET"
    assert log_entry["url_host"] == "host.docker.internal"
    assert log_entry["url_path"] == "/core/v1/foo"
    assert log_entry["error_type"] == "ConnectError"
    assert "Name or service not known" in log_entry["error_message"]
