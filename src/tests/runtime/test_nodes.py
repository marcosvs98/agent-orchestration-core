import contextlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.execution.services.graph_runtime.nodes import (
    ToolSelectionNode,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType
from domain.tools.schemas.tools import AvailableTool


class _FakeObservationHandle:
    def __init__(self, *, tracer, as_type: str, name: str, input_payload: dict):
        self._tracer = tracer
        self._as_type = as_type
        self._name = name
        self._input = input_payload
        self._output = None

    def update(self, **kwargs) -> None:
        return None

    def success(self, *, output, metadata=None, **kwargs) -> None:
        self._output = output

    def error(
        self,
        *,
        error_type: str,
        error_message: str,
        output=None,
        metadata=None,
        level: str = "ERROR",
        status_message: str | None = None,
        **kwargs,
    ) -> None:
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


class _FakeTracer:
    def __init__(self):
        self.records = []

    @contextlib.contextmanager
    def observe(self, *, as_type, name, input, **kwargs):
        handle = _FakeObservationHandle(
            tracer=self, as_type=as_type, name=name, input_payload=input
        )
        try:
            yield handle
        finally:
            handle.finalize()


def _make_context(**overrides):
    defaults = dict(
        tenant_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


def _build_tool_selection_node(
    retriever_return=None,
    agent_version=None,
    agent_version_id=None,
    llm_fallback=None,
    tool_catalog_indexer=None,
    tracer=None,
):
    tracer = tracer or _FakeTracer()
    retriever = MagicMock()
    if retriever_return is not None:
        retriever.retrieve_candidates = AsyncMock(return_value=retriever_return)
    else:
        retriever.retrieve_candidates = AsyncMock(return_value=([], []))

    agents_repo = MagicMock()
    agents_repo.get_agent_version_id_by_node_id = AsyncMock(
        return_value=agent_version_id or uuid.uuid4()
    )
    agents_repo.get_agent_version = AsyncMock(return_value=agent_version)

    return ToolSelectionNode(
        tracer=tracer,
        tool_catalog_retriever=retriever,
        agents_repository=agents_repo,
        llm_fallback=llm_fallback,
        tool_catalog_indexer=tool_catalog_indexer,
    ), retriever, agents_repo


@pytest.mark.asyncio
async def test_tool_selection_returns_candidates_from_semantic_retrieval():
    tool = AvailableTool(
        name="get-weather",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        retrieval_score=0.95,
    )
    rag_config_id = uuid.uuid4()
    agent_version = SimpleNamespace(rag_config_id=rag_config_id)

    node, retriever, _ = _build_tool_selection_node(
        retriever_return=([tool], [{"tool_config_id": str(tool.tool_config_id), "score": 0.95}]),
        agent_version=agent_version,
    )

    context = _make_context(
        input_payload={"user_input": "what is the weather?"},
        available_tools=[tool],
    )

    result = await node.execute(context)

    assert result.status == "SUCCESS"
    assert len(result.data["result"]) == 1
    assert result.data["result"][0]["selected_tool"]["name"] == "get-weather"
    assert result.data["result"][0]["confidence"] == 0.95
    retriever.retrieve_candidates.assert_called_once()


@pytest.mark.asyncio
async def test_tool_selection_returns_all_tools_when_no_user_input():
    tool = AvailableTool(
        name="tool-a", tool_id=uuid.uuid4(), tool_config_id=uuid.uuid4()
    )
    agent_version = SimpleNamespace(rag_config_id=uuid.uuid4())

    node, retriever, _ = _build_tool_selection_node(agent_version=agent_version)

    context = _make_context(
        input_payload={},
        available_tools=[tool],
    )

    result = await node.execute(context)

    assert result.status == "SUCCESS"
    assert len(result.data["result"]) == 1
    assert result.data["result"][0]["confidence"] == 0.5
    retriever.retrieve_candidates.assert_not_called()


@pytest.mark.asyncio
async def test_tool_selection_returns_all_tools_when_no_rag_config():
    tool = AvailableTool(
        name="tool-a", tool_id=uuid.uuid4(), tool_config_id=uuid.uuid4()
    )
    node, retriever, _ = _build_tool_selection_node(agent_version=None)

    context = _make_context(
        input_payload={"user_input": "query"},
        available_tools=[tool],
    )

    result = await node.execute(context)

    assert result.status == "SUCCESS"
    assert len(result.data["result"]) == 1
    retriever.retrieve_candidates.assert_not_called()


@pytest.mark.asyncio
async def test_tool_selection_updates_context_available_tools():
    original_tool = AvailableTool(
        name="tool-keep", tool_id=uuid.uuid4(), tool_config_id=uuid.uuid4()
    )
    filtered_tool = AvailableTool(
        name="tool-keep",
        tool_id=original_tool.tool_id,
        tool_config_id=original_tool.tool_config_id,
        retrieval_score=0.9,
    )
    other_tool = AvailableTool(
        name="tool-discard", tool_id=uuid.uuid4(), tool_config_id=uuid.uuid4()
    )
    agent_version = SimpleNamespace(rag_config_id=uuid.uuid4())

    node, _, _ = _build_tool_selection_node(
        retriever_return=([filtered_tool], []),
        agent_version=agent_version,
    )

    context = _make_context(
        input_payload={"user_input": "do something"},
        available_tools=[original_tool, other_tool],
    )

    await node.execute(context)

    assert len(context.available_tools) == 1
    assert context.available_tools[0].name == "tool-keep"


@pytest.mark.asyncio
async def test_tool_selection_writes_next_state():
    tool = AvailableTool(
        name="tool-1",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        retrieval_score=0.8,
    )
    agent_version = SimpleNamespace(rag_config_id=uuid.uuid4())

    node, _, _ = _build_tool_selection_node(
        retriever_return=([tool], []),
        agent_version=agent_version,
    )

    context = _make_context(
        input_payload={"user_input": "find tool"},
        available_tools=[tool],
    )

    result = await node.execute(context)

    assert result.next_state is not None
    assert "ToolSelectionNode" in result.next_state


@pytest.mark.asyncio
async def test_tool_selection_delegates_to_llm_fallback_when_low_confidence():
    tool = AvailableTool(
        name="checkout",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        operation_id="checkout",
        method="POST",
        path="/checkout",
        retrieval_score=0.4,
    )
    agent_version = SimpleNamespace(rag_config_id=uuid.uuid4())
    llm_result = NodeResult(
        node=NodeType.ToolSelectionNode,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                {
                    "selected_tool": {
                        "name": tool.name,
                        "tool_config_id": str(tool.tool_config_id),
                    },
                    "confidence": 0.91,
                }
            ]
        },
        next_state={},
    )
    llm_fallback = MagicMock()
    llm_fallback.execute = AsyncMock(return_value=llm_result)
    tool_catalog_indexer = MagicMock()
    tool_catalog_indexer.index_document = AsyncMock(return_value=None)

    node, retriever, _ = _build_tool_selection_node(
        retriever_return=([tool], [{"tool_config_id": str(tool.tool_config_id), "score": 0.4}]),
        agent_version=agent_version,
        llm_fallback=llm_fallback,
        tool_catalog_indexer=tool_catalog_indexer,
    )

    context = _make_context(
        input_payload={"user_input": "execute o checkout dos debitos"},
        available_tools=[tool],
    )
    result = await node.execute(context)

    assert result == llm_result
    assert retriever.retrieve_candidates.called
    llm_fallback.execute.assert_called_once()
    tool_catalog_indexer.index_document.assert_called_once()


@pytest.mark.asyncio
async def test_tool_selection_instrumentation_contains_scores_and_evidence():
    tool = AvailableTool(
        name="createExpense",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        retrieval_score=0.92,
    )
    evidence = [{"tool_config_id": str(tool.tool_config_id), "score": 0.92}]
    tracer = _FakeTracer()
    agent_version = SimpleNamespace(rag_config_id=uuid.uuid4())
    node, _, _ = _build_tool_selection_node(
        retriever_return=([tool], evidence),
        agent_version=agent_version,
        tracer=tracer,
    )
    context = _make_context(
        input_payload={"user_input": "paguei no cartao"},
        available_tools=[tool],
    )

    await node.execute(context)

    retrieval_record = next(
        record
        for record in tracer.records
        if record["name"] == "domain.execution.nodes.tool_selection.semantic_retrieval"
    )
    execute_record = next(
        record
        for record in tracer.records
        if record["name"] == "domain.execution.nodes.tool_selection.execute"
    )
    assert retrieval_record["output"]["candidate_count"] == 1
    assert retrieval_record["output"]["evidence"] == evidence
    assert retrieval_record["output"]["selected_tools"][0]["retrieval_score"] == 0.92
    assert execute_record["output"]["selection_mode"] == "semantic"
    assert execute_record["output"]["best_score"] == 0.92
    assert execute_record["output"]["selected_tools"][0]["name"] == "createExpense"


@pytest.mark.asyncio
async def test_tool_selection_instrumentation_contains_fallback_reason():
    tool = AvailableTool(
        name="createExpense",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        operation_id="createExpense",
        method="POST",
        path="/expenses",
        retrieval_score=0.31,
    )
    tracer = _FakeTracer()
    agent_version = SimpleNamespace(rag_config_id=uuid.uuid4())
    llm_result = NodeResult(
        node=NodeType.ToolSelectionNode,
        status=NodeExecutionStatus.SUCCESS,
        data={
            "result": [
                {
                    "selected_tool": {
                        "name": tool.name,
                        "tool_config_id": str(tool.tool_config_id),
                    },
                    "confidence": 0.95,
                }
            ]
        },
        next_state={},
    )
    llm_fallback = MagicMock()
    llm_fallback.execute = AsyncMock(return_value=llm_result)
    tool_catalog_indexer = MagicMock()
    tool_catalog_indexer.index_document = AsyncMock(return_value=None)
    node, _, _ = _build_tool_selection_node(
        retriever_return=([tool], []),
        agent_version=agent_version,
        llm_fallback=llm_fallback,
        tool_catalog_indexer=tool_catalog_indexer,
        tracer=tracer,
    )
    context = _make_context(
        input_payload={"user_input": "paguei no cartao"},
        available_tools=[tool],
    )

    await node.execute(context)

    execute_record = next(
        record
        for record in tracer.records
        if record["name"] == "domain.execution.nodes.tool_selection.execute"
    )
    assert execute_record["output"]["selection_mode"] == "llm_fallback"
    assert execute_record["output"]["fallback_reason"] == "below_confidence_threshold"
    assert execute_record["output"]["semantic_evidence_count"] == 0


def test_node_attributes():
    assert ToolSelectionNode.node_type == "ToolSelectionNode"
    assert ToolSelectionNode.side_effect is False
    assert ToolSelectionNode.deterministic is False
