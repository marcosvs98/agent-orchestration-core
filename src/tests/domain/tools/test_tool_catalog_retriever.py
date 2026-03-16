from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.rag.schemas.rag import RagContext, RagContextItem, RagContextReason
from domain.tools.schemas.tools import AvailableTool
from domain.tools.services.tool_catalog_retriever import ToolCatalogRetriever


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


@pytest.mark.asyncio
async def test_retrieve_candidates_returns_top_k_ranked_by_score():
    tool_config_id_1 = uuid4()
    tool_config_id_2 = uuid4()
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
    tracer = _FakeTracer()
    retriever = ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
    )
    available_tools = [
        AvailableTool(name="tool-1", tool_id=uuid4(), tool_config_id=tool_config_id_1),
        AvailableTool(name="tool-2", tool_id=uuid4(), tool_config_id=tool_config_id_2),
    ]

    candidates, evidence = await retriever.retrieve_candidates(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="find second tool",
        available_tools=available_tools,
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
async def test_retrieve_candidates_falls_back_to_available_tools_when_empty_context():
    rag_runtime_service = MagicMock()
    rag_runtime_service.get_context = AsyncMock(
        return_value=RagContext(
            context_items=[],
            eligible=True,
            reason=RagContextReason.NO_MATCHES,
        )
    )
    tracer = _FakeTracer()
    retriever = ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
    )
    available_tools = [
        AvailableTool(name="tool-1", tool_id=uuid4(), tool_config_id=uuid4()),
        AvailableTool(name="tool-2", tool_id=uuid4(), tool_config_id=uuid4()),
    ]

    candidates, evidence = await retriever.retrieve_candidates(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="find tool",
        available_tools=available_tools,
        top_k=1,
    )

    assert candidates == []
    assert evidence == []
    record = tracer.records[0]
    assert record["name"] == "domain.tools.tool_catalog_retriever.retrieve_candidates"
    assert record["output"]["fallback_used"] is False
    assert record["output"]["candidate_count"] == 0
    assert record["output"]["evidence"] == []


@pytest.mark.asyncio
async def test_retrieve_candidates_forwards_tool_intent_filter_to_rag():
    tool_config_id = uuid4()
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
    retriever = ToolCatalogRetriever(
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
    )
    available_tools = [
        AvailableTool(name="tool-1", tool_id=uuid4(), tool_config_id=tool_config_id),
    ]

    await retriever.retrieve_candidates(
        tenant_id=uuid4(),
        rag_config_id=uuid4(),
        user_input="find tool",
        available_tools=available_tools,
        top_k=1,
        tool_intent_filter=command",
    )

    kwargs = rag_runtime_service.get_context.call_args.kwargs
    assert kwargs["filters_override"]["tool_intent"] == "command"
