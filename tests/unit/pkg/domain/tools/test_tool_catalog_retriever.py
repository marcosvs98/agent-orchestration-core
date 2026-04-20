from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.rag.schemas.rag import RagContext, RagContextItem, RagContextReason
from domain.tools.services.tool_catalog_retriever import (
    MAX_TOOL_CATALOG_TOP_K,
    ToolCatalogRetriever,
)


class _FakeTracer:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def observe(self, *, as_type, name, input):
        handle = _FakeObservationHandle(
            tracer=self,
            as_type=as_type,
            name=name,
            input_payload=input,
        )
        return _yield_handle(handle)


class _FakeObservationHandle:
    def __init__(self, *, tracer, as_type: str, name: str, input_payload: dict):
        self._tracer = tracer
        self._as_type = as_type
        self._name = name
        self._input = input_payload
        self._output = None

    def success(self, *, output, metadata=None, **kwargs) -> None:
        self._output = output

    def finalize(self) -> None:
        self._tracer.records.append(
            {
                "as_type": self._as_type,
                "name": self._name,
                "input": self._input,
                "output": self._output,
            }
        )


@contextlib.contextmanager
def _yield_handle(handle):
    try:
        yield handle
    finally:
        handle.finalize()


def _cfg_tool_row(
    *,
    tool_config_id,
    tool_id,
    name: str,
):
    cfg = MagicMock()
    cfg.tool_config_id = tool_config_id
    cfg.tool_id = tool_id
    cfg.config = {"summary": "s", "operation_id": "op", "method": "POST", "path": "/p"}
    tool = MagicMock()
    tool.name = name
    tool.tool_id = tool_id
    return cfg, tool


@pytest.mark.asyncio
async def test_retrieve_candidates_returns_top_k_ranked_by_score():
    tool_config_id_1 = uuid4()
    tool_config_id_2 = uuid4()
    tool_id_1 = uuid4()
    tool_id_2 = uuid4()
    rag_runtime_service = MagicMock()
    rag_runtime_service.get_context = AsyncMock(
        return_value=RagContext(
            context_items=[
                RagContextItem(
                    document_id=uuid4(),
                    chunk_id=uuid4(),
                    content="tool one",
                    score=0.4,
                    metadata={"tool_config_id": str(tool_config_id_1)},
                ),
                RagContextItem(
                    document_id=uuid4(),
                    chunk_id=uuid4(),
                    content="tool two",
                    score=0.9,
                    metadata={"tool_config_id": str(tool_config_id_2)},
                ),
                RagContextItem(
                    document_id=uuid4(),
                    chunk_id=uuid4(),
                    content="tool one better chunk",
                    score=0.8,
                    metadata={"tool_config_id": str(tool_config_id_1)},
                ),
            ],
            eligible=True,
            reason=RagContextReason.OK,
        )
    )
    tools_repository = MagicMock()

    async def _repo_side_effect(*, tenant_id, tool_config_ids):
        by = {tool_config_id_1: _cfg_tool_row(
            tool_config_id=tool_config_id_1, tool_id=tool_id_1, name="tool-1"
        ), tool_config_id_2: _cfg_tool_row(
            tool_config_id=tool_config_id_2, tool_id=tool_id_2, name="tool-2"
        )}
        return [by[i] for i in tool_config_ids if i in by]

    tools_repository.list_published_tool_configs_with_tools_by_config_ids = (
        AsyncMock(side_effect=_repo_side_effect)
    )
    tracer = _FakeTracer()
    retriever = ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
        tools_repository=tools_repository,
    )

    candidates, evidence = await retriever.retrieve_candidates(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="find second tool",
        top_k=2,
    )

    assert [item.tool_config_id for item in candidates] == [
        tool_config_id_2,
        tool_config_id_1,
    ]
    assert len(evidence) == 2
    assert evidence[0]["tool_config_id"] == str(tool_config_id_2)
    assert candidates[0].retrieval_score == pytest.approx(0.9)
    record = tracer.records[0]
    assert record["name"] == "domain.tools.tool_catalog_retriever.retrieve_candidates"
    assert record["output"]["fallback_used"] is False
    assert record["output"]["candidate_count"] == 2
    assert len(record["output"]["evidence"]) == 2


@pytest.mark.asyncio
async def test_retrieve_candidates_returns_empty_when_no_rag_hits():
    rag_runtime_service = MagicMock()
    rag_runtime_service.get_context = AsyncMock(
        return_value=RagContext(
            context_items=[],
            eligible=True,
            reason=RagContextReason.NO_MATCHES,
        )
    )
    tracer = _FakeTracer()
    tools_repository = MagicMock()
    tools_repository.list_published_tool_configs_with_tools_by_config_ids = AsyncMock()
    retriever = ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
        tools_repository=tools_repository,
    )

    candidates, evidence = await retriever.retrieve_candidates(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="find tool",
        top_k=1,
    )

    assert candidates == []
    assert evidence == []
    tools_repository.list_published_tool_configs_with_tools_by_config_ids.assert_not_called()
    record = tracer.records[0]
    assert record["name"] == "domain.tools.tool_catalog_retriever.retrieve_candidates"
    assert record["output"]["fallback_used"] is False
    assert record["output"]["candidate_count"] == 0
    assert record["output"]["evidence"] == []


@pytest.mark.asyncio
async def test_retrieve_candidates_forwards_tool_intent_filter_to_rag():
    tool_config_id = uuid4()
    tool_id = uuid4()
    rag_runtime_service = MagicMock()
    rag_runtime_service.get_context = AsyncMock(
        return_value=RagContext(
            context_items=[
                RagContextItem(
                    document_id=uuid4(),
                    chunk_id=uuid4(),
                    content="tool",
                    score=0.7,
                    metadata={"tool_config_id": str(tool_config_id)},
                )
            ],
            eligible=True,
            reason=RagContextReason.OK,
        )
    )
    tracer = _FakeTracer()
    tools_repository = MagicMock()
    tools_repository.list_published_tool_configs_with_tools_by_config_ids = AsyncMock(
        return_value=[
            _cfg_tool_row(
                tool_config_id=tool_config_id, tool_id=tool_id, name="tool-1"
            )
        ]
    )
    retriever = ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
        tools_repository=tools_repository,
    )

    await retriever.retrieve_candidates(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="find tool",
        top_k=1,
        tool_intent_filter="command",
    )

    kwargs = rag_runtime_service.get_context.call_args.kwargs
    assert kwargs["filters_override"]["tool_intent"] == "command"


@pytest.mark.asyncio
async def test_retrieve_candidates_caps_top_k_at_max():
    rag_runtime_service = MagicMock()
    items = []
    for i in range(10):
        tid = uuid4()
        items.append(
            RagContextItem(
                document_id=uuid4(),
                chunk_id=uuid4(),
                content=f"t{i}",
                score=float(i) / 10.0,
                metadata={"tool_config_id": str(tid)},
            )
        )
    rag_runtime_service.get_context = AsyncMock(
        return_value=RagContext(
            context_items=items,
            eligible=True,
            reason=RagContextReason.OK,
        )
    )
    tools_repository = MagicMock()

    async def _repo_side_effect(*, tenant_id, tool_config_ids):
        out = []
        for cid in tool_config_ids:
            out.append(
                _cfg_tool_row(
                    tool_config_id=cid, tool_id=uuid4(), name=f"n-{cid.hex[:6]}"
                )
            )
        return out

    tools_repository.list_published_tool_configs_with_tools_by_config_ids = (
        AsyncMock(side_effect=_repo_side_effect)
    )
    tracer = _FakeTracer()
    retriever = ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
        tools_repository=tools_repository,
    )

    candidates, _ = await retriever.retrieve_candidates(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="many",
        top_k=100,
    )

    assert len(candidates) == MAX_TOOL_CATALOG_TOP_K
