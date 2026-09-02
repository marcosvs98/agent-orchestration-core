"""ToolCatalogRetriever — semantic tool ranking over the tool-catalog RAG corpus.

This file previously targeted `retrieve_candidates`, which returned `(candidates, evidence)` and
emitted its own trace span. Commit c51f2f8 replaced it with `retrieve_tools`, which returns
`list[AvailableTool]` and leaves tracing to the RAG layer. The assertions below cover the behaviour
that survived the rename: best-score-per-tool ranking, chunk dedupe, the recall multiplier, the
agent-version binding filter, and not touching the repository when retrieval is empty.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.rag.schemas.rag import RagContext, RagContextItem, RagContextReason
from domain.tools.services.tool_catalog_retriever import (
    MAX_TOOL_CATALOG_TOP_K,
    TOOL_CATALOG_RECALL_TOP_K_MULTIPLIER,
    TOOL_CATALOG_SIMILARITY_THRESHOLD_CAP,
    ToolCatalogRetriever,
)


class _FakeTracer:
    @contextlib.contextmanager
    def observe(self, **_):
        yield MagicMock()


def _cfg_tool_row(*, tool_config_id, tool_id, name: str):
    cfg = MagicMock()
    cfg.tool_config_id = tool_config_id
    cfg.tool_id = tool_id
    cfg.config = {"summary": "s", "operation_id": "op", "method": "POST", "path": "/p"}
    tool = MagicMock()
    tool.name = name
    tool.tool_id = tool_id
    return cfg, tool


def _context(*items: RagContextItem, reason: RagContextReason = RagContextReason.OK) -> RagContext:
    return RagContext(context_items=list(items), eligible=True, reason=reason)


def _item(tool_config_id, score: float, content: str = "chunk") -> RagContextItem:
    return RagContextItem(
        document_id=uuid4(),
        chunk_id=uuid4(),
        content=content,
        score=score,
        metadata={"tool_config_id": str(tool_config_id)},
    )


def _retriever(rag_runtime_service, tools_repository) -> ToolCatalogRetriever:
    return ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=_FakeTracer(),
        tools_repository=tools_repository,
    )


def _repository(rows_by_config_id: dict) -> MagicMock:
    repository = MagicMock()

    async def side_effect(*, tenant_id, tool_config_ids):
        return [rows_by_config_id[i] for i in tool_config_ids if i in rows_by_config_id]

    repository.list_published_tool_configs_with_tools_by_config_ids = AsyncMock(
        side_effect=side_effect
    )
    repository.list_tool_bindings_by_agent_version_id = AsyncMock(return_value=[])
    return repository


@pytest.mark.asyncio
async def test_tools_are_ranked_by_best_chunk_score_per_tool():
    first, second = uuid4(), uuid4()
    rag = MagicMock()
    rag.get_context = AsyncMock(
        return_value=_context(
            _item(first, 0.4, "tool one"),
            _item(second, 0.9, "tool two"),
            _item(first, 0.8, "tool one, better chunk"),
        )
    )
    repository = _repository(
        {
            first: _cfg_tool_row(tool_config_id=first, tool_id=uuid4(), name="tool-1"),
            second: _cfg_tool_row(tool_config_id=second, tool_id=uuid4(), name="tool-2"),
        }
    )

    tools = await _retriever(rag, repository).retrieve_tools(
        tenant_id=uuid4(), rag_config_id=uuid4(), user_input="find second tool", top_k=2
    )

    assert [tool.tool_config_id for tool in tools] == [second, first]
    assert tools[0].retrieval_score == pytest.approx(0.9)
    assert tools[1].retrieval_score == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_no_rag_hits_returns_no_tools_and_skips_the_repository():
    rag = MagicMock()
    rag.get_context = AsyncMock(return_value=_context(reason=RagContextReason.NO_MATCHES))
    repository = _repository({})

    tools = await _retriever(rag, repository).retrieve_tools(
        tenant_id=uuid4(), rag_config_id=uuid4(), user_input="find tool", top_k=1
    )

    assert tools == []
    repository.list_published_tool_configs_with_tools_by_config_ids.assert_awaited_once()
    assert (
        repository.list_published_tool_configs_with_tools_by_config_ids.await_args.kwargs[
            "tool_config_ids"
        ]
        == []
    )


@pytest.mark.asyncio
async def test_retrieval_uses_the_catalog_filters_and_recall_multiplier():
    rag = MagicMock()
    rag.get_context = AsyncMock(return_value=_context())

    await _retriever(rag, _repository({})).retrieve_tools(
        tenant_id=uuid4(), rag_config_id=uuid4(), user_input="find tool", top_k=2
    )

    kwargs = rag.get_context.call_args.kwargs
    assert kwargs["filters_override"] == {
        "source": "tool_catalog",
        "doc_type": "tool_catalog",
        "category": "TOOL_CATALOG",
    }
    assert kwargs["top_k_override"] == 2 * TOOL_CATALOG_RECALL_TOP_K_MULTIPLIER
    assert kwargs["similarity_threshold_cap"] == TOOL_CATALOG_SIMILARITY_THRESHOLD_CAP
    assert kwargs["user_id"] is None


@pytest.mark.asyncio
async def test_absent_top_k_falls_back_to_the_catalog_maximum():
    rag = MagicMock()
    rag.get_context = AsyncMock(return_value=_context())

    await _retriever(rag, _repository({})).retrieve_tools(
        tenant_id=uuid4(), rag_config_id=uuid4(), user_input="find tool"
    )

    assert (
        rag.get_context.call_args.kwargs["top_k_override"]
        == MAX_TOOL_CATALOG_TOP_K * TOOL_CATALOG_RECALL_TOP_K_MULTIPLIER
    )


@pytest.mark.asyncio
async def test_agent_version_bindings_restrict_the_result():
    bound, unbound = uuid4(), uuid4()
    agent_version_id = uuid4()
    rag = MagicMock()
    rag.get_context = AsyncMock(return_value=_context(_item(unbound, 0.9), _item(bound, 0.5)))
    repository = _repository(
        {
            bound: _cfg_tool_row(tool_config_id=bound, tool_id=uuid4(), name="bound"),
            unbound: _cfg_tool_row(tool_config_id=unbound, tool_id=uuid4(), name="unbound"),
        }
    )
    repository.list_tool_bindings_by_agent_version_id = AsyncMock(
        return_value=[MagicMock(tool_config_id=bound)]
    )

    tools = await _retriever(rag, repository).retrieve_tools(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="find tool",
        agent_version_id=agent_version_id,
    )

    assert [tool.tool_config_id for tool in tools] == [bound]


@pytest.mark.asyncio
async def test_chunks_without_a_tool_config_id_are_ignored():
    valid = uuid4()
    rag = MagicMock()
    rag.get_context = AsyncMock(
        return_value=RagContext(
            context_items=[
                RagContextItem(
                    document_id=uuid4(),
                    chunk_id=uuid4(),
                    content="orphan chunk",
                    score=0.99,
                    metadata={},
                ),
                RagContextItem(
                    document_id=uuid4(),
                    chunk_id=uuid4(),
                    content="malformed id",
                    score=0.98,
                    metadata={"tool_config_id": "not-a-uuid"},
                ),
                _item(valid, 0.5),
            ],
            eligible=True,
            reason=RagContextReason.OK,
        )
    )
    repository = _repository(
        {valid: _cfg_tool_row(tool_config_id=valid, tool_id=uuid4(), name="valid")}
    )

    tools = await _retriever(rag, repository).retrieve_tools(
        tenant_id=uuid4(), rag_config_id=uuid4(), user_input="find tool"
    )

    assert [tool.tool_config_id for tool in tools] == [valid]
