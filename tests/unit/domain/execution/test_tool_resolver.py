"""Behavioural tests for ToolResolver (retrieve tools → LLM path vs empty; indexing side-effect)."""

from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes.tool_resolver import ToolResolver
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType
from domain.tools.schemas.tools import AvailableTool


def _ctx(node_id: str | None = None) -> ExecutionContext:
    nid = str(node_id or uuid4())
    return ExecutionContext.model_validate(
        {
            "tenant_id": uuid4(),
            "interaction_id": uuid4(),
            "user_id": "u1",
            "session_id": uuid4(),
            "input_payload": {"user_input": "book a flight"},
            "flow_id": uuid4(),
            "flow_version_id": uuid4(),
            "flow_run_id": uuid4(),
            "correlation_id": uuid4(),
            "current_node_id": nid,
        }
    )


def _resolver_mocks(
    *,
    tools: list[AvailableTool],
    indexer: object | None = MagicMock(),
) -> ToolResolver:
    tracer = MagicMock(spec=RuntimeTracerPort)
    tracer.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    llm = MagicMock()
    prompt_resolver = MagicMock()
    agents = MagicMock()
    agents.resolve_effective_rag_config_id_for_node = AsyncMock(return_value=uuid4())
    agents.get_agent_version_id_by_node_id = AsyncMock(return_value=uuid4())
    retriever = MagicMock()
    retriever.retrieve_tools = AsyncMock(return_value=tools)
    return ToolResolver(
        tracer=tracer,
        llm_executor=llm,
        prompt_resolver=prompt_resolver,
        agent_runtime_resolver=None,
        completion_budget_policy=None,
        tool_catalog_retriever=retriever,
        agents_repository=agents,
        tool_catalog_indexer=indexer,
    )


@pytest.mark.asyncio
async def test_execute_returns_empty_result_when_no_tools_retrieved() -> None:
    resolver = _resolver_mocks(tools=[])
    out = await resolver.execute(_ctx(), config={"top_k": 3})
    assert out.node == NodeType.ToolResolver
    assert out.status == NodeExecutionStatus.SUCCESS
    assert out.data["result"] == []


@pytest.mark.asyncio
async def test_execute_runs_llm_and_drains_background_index_task() -> None:
    tool = AvailableTool(
        name="t1",
        tool_id=uuid4(),
        tool_config_id=uuid4(),
    )
    # No indexer: background task exits immediately without awaiting MagicMocks.
    resolver = _resolver_mocks(tools=[tool], indexer=None)
    llm_out = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                {
                    "selected_tool": {
                        "name": "t1",
                        "tool_config_id": str(tool.tool_config_id),
                    },
                    "confidence": 0.9,
                }
            ]
        },
    )
    pending: list[Any] = []

    def _capture_task(coro: Any, name: str | None = None) -> MagicMock:
        pending.append(coro)
        t = MagicMock()
        t.done = lambda: True
        return t

    with (
        patch.object(
            resolver,
            "_run_llm_after_setup",
            new=AsyncMock(return_value=llm_out),
        ),
        patch("asyncio.create_task", side_effect=_capture_task),
    ):
        out = await resolver.execute(_ctx(), config={})
    assert out is llm_out
    assert len(pending) == 1
    await pending[0]


@pytest.mark.asyncio
async def test_index_post_llm_skips_when_indexer_missing() -> None:
    resolver = _resolver_mocks(tools=[], indexer=None)
    llm_out = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={"result": []},
    )
    # Should not raise even with indexer None
    await resolver._index_post_llm_selection(
        tenant_id=uuid4(),
        user_input="x",
        retrieved_tools=[],
        llm_result=llm_out,
        config={},
    )


@pytest.mark.asyncio
async def test_index_post_llm_indexes_selected_tool_when_confidence_ok() -> None:
    tid = uuid4()
    cfg_id = uuid4()
    tool = AvailableTool(name="api", tool_id=tid, tool_config_id=cfg_id)
    indexer = MagicMock()
    indexer.index_document = AsyncMock()
    resolver = _resolver_mocks(tools=[tool], indexer=indexer)
    llm_out = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                {
                    "selected_tool": {
                        "name": "api",
                        "tool_config_id": str(cfg_id),
                    },
                    "confidence": 0.95,
                }
            ]
        },
    )
    tenant = uuid4()
    await resolver._index_post_llm_selection(
        tenant_id=tenant,
        user_input="hello",
        retrieved_tools=[tool],
        llm_result=llm_out,
        config={"min_indexing_confidence": 0.5},
    )
    indexer.index_document.assert_awaited_once()
    call_kw = indexer.index_document.await_args.kwargs
    assert call_kw["tenant_id"] == tenant
    assert call_kw["document"].tool_id == tid


@pytest.mark.asyncio
async def test_index_post_llm_respects_min_indexing_confidence() -> None:
    cfg_id = uuid4()
    tool = AvailableTool(name="api", tool_id=uuid4(), tool_config_id=cfg_id)
    indexer = MagicMock()
    indexer.index_document = AsyncMock()
    resolver = _resolver_mocks(tools=[tool], indexer=indexer)
    llm_out = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                {
                    "selected_tool": {
                        "name": "api",
                        "tool_config_id": str(cfg_id),
                    },
                    "confidence": 0.1,
                }
            ]
        },
    )
    await resolver._index_post_llm_selection(
        tenant_id=uuid4(),
        user_input="x",
        retrieved_tools=[tool],
        llm_result=llm_out,
        config={"min_indexing_confidence": 0.9},
    )
    indexer.index_document.assert_not_called()


def test_extract_selected_tools_parses_nested_shape() -> None:
    nr = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                {
                    "selected_tool": {"name": "a", "tool_config_id": "tid"},
                    "confidence": 0.5,
                }
            ]
        },
    )
    sel = ToolResolver._extract_selected_tools(nr)
    assert sel == [
        {"name": "a", "tool_config_id": "tid", "confidence": 0.5},
    ]


def test_extract_selected_tools_ignores_bad_items() -> None:
    nr = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={"result": "not-a-list"},
    )
    assert ToolResolver._extract_selected_tools(nr) == []


def test_extract_selected_tools_skips_non_dict_and_non_dict_selected_tool() -> None:
    nr = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                "skip",
                {"selected_tool": "not-dict"},
                {
                    "selected_tool": {"name": "x", "tool_config_id": "y"},
                    "confidence": 1.0,
                },
            ]
        },
    )
    assert len(ToolResolver._extract_selected_tools(nr)) == 1


@pytest.mark.asyncio
async def test_index_post_llm_no_selections_returns_early() -> None:
    resolver = _resolver_mocks(tools=[], indexer=MagicMock())
    indexer = resolver.tool_catalog_indexer
    assert indexer is not None
    indexer.index_document = AsyncMock()
    llm_out = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={"result": []},
    )
    await resolver._index_post_llm_selection(
        tenant_id=uuid4(),
        user_input="x",
        retrieved_tools=[],
        llm_result=llm_out,
        config={},
    )
    indexer.index_document.assert_not_called()


@pytest.mark.asyncio
async def test_index_post_llm_skips_unknown_tool_config_id() -> None:
    cfg_id = uuid4()
    tool = AvailableTool(name="api", tool_id=uuid4(), tool_config_id=cfg_id)
    indexer = MagicMock()
    indexer.index_document = AsyncMock()
    resolver = _resolver_mocks(tools=[tool], indexer=indexer)
    llm_out = NodeResult(
        node=NodeType.ToolResolver,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                {
                    "selected_tool": {
                        "name": "api",
                        "tool_config_id": str(uuid4()),
                    },
                    "confidence": 1.0,
                }
            ]
        },
    )
    await resolver._index_post_llm_selection(
        tenant_id=uuid4(),
        user_input="x",
        retrieved_tools=[tool],
        llm_result=llm_out,
        config={},
    )
    indexer.index_document.assert_not_called()
