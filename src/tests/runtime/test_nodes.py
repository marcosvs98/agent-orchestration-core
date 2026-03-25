import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.execution.services.graph_runtime.nodes import ToolResolver
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.llm.schemas.llm import LLMResult
from domain.prompts.schemas.prompt import NodeType, ResolvedPrompt
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
        interaction_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        input_payload={},
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        current_node_id=str(uuid.uuid4()),
        metadata={"runtime_policy": {"llm": {"model_alias": "test-model"}}},
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


def _build_tool_selection_node(
    retriever_return=None,
    rag_config_id=None,
    llm_output=None,
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
    rid = rag_config_id or uuid.uuid4()
    agents_repo.resolve_effective_rag_config_id_for_node = AsyncMock(return_value=rid)

    llm_executor = MagicMock()
    tool = None
    if retriever_return and retriever_return[0]:
        tool = retriever_return[0][0]
    default_llm_out: dict = {"result": []}
    if tool is not None:
        default_llm_out = {
            "result": [
                {
                    "intent_type": "command",
                    "selected_tool": {
                        "name": tool.name,
                        "tool_config_id": str(tool.tool_config_id),
                    },
                    "confidence": 0.91,
                }
            ]
        }
    out = llm_output if llm_output is not None else default_llm_out
    llm_executor.execute_llm = AsyncMock(return_value=LLMResult(output=out))

    prompt_resolver = MagicMock()
    prompt_resolver.resolve = AsyncMock(
        return_value=ResolvedPrompt(
            prompt_text="select",
            output_schema={"type": "object"},
            input_schema={},
        )
    )

    node = ToolResolver(
        tracer=tracer,
        llm_executor=llm_executor,
        prompt_resolver=prompt_resolver,
        agent_runtime_resolver=None,
        completion_budget_policy=None,
        tool_catalog_retriever=retriever,
        agents_repository=agents_repo,
        tool_catalog_indexer=tool_catalog_indexer,
    )
    return node, retriever, agents_repo, llm_executor


@pytest.mark.asyncio
async def test_tool_selection_rag_then_llm_passes_candidates_to_llm():
    tool = AvailableTool(
        name="get-weather",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        retrieval_score=0.95,
    )
    rag_config_id = uuid.uuid4()

    node, retriever, _, llm_executor = _build_tool_selection_node(
        retriever_return=([tool], [{"tool_config_id": str(tool.tool_config_id), "score": 0.95}]),
        rag_config_id=rag_config_id,
    )

    context = _make_context(input_payload={"user_input": "what is the weather?"})

    result = await node.execute(context)

    assert result.status == "SUCCESS"
    assert len(result.data["result"]) == 1
    assert result.data["result"][0]["selected_tool"]["name"] == "get-weather"
    retriever.retrieve_candidates.assert_called_once()
    rc_kw = retriever.retrieve_candidates.call_args.kwargs
    assert "available_tools" not in rc_kw
    assert rc_kw["rag_config_id"] == rag_config_id
    llm_executor.execute_llm.assert_called_once()
    req = llm_executor.execute_llm.call_args.kwargs["request"]
    assert len(req.available_tools) == 1
    assert req.available_tools[0].tool_config_id == tool.tool_config_id


@pytest.mark.asyncio
async def test_tool_selection_empty_when_no_user_input():
    rag_config_id = uuid.uuid4()
    node, retriever, _, llm_executor = _build_tool_selection_node(
        rag_config_id=rag_config_id,
    )

    context = _make_context(input_payload={})

    result = await node.execute(context)

    assert result.status == "SUCCESS"
    assert result.data["result"] == []
    retriever.retrieve_candidates.assert_not_called()
    llm_executor.execute_llm.assert_not_called()


@pytest.mark.asyncio
async def test_tool_selection_empty_when_no_rag_config():
    tracer = _FakeTracer()
    retriever = MagicMock()
    retriever.retrieve_candidates = AsyncMock()
    agents_repo = MagicMock()
    agents_repo.resolve_effective_rag_config_id_for_node = AsyncMock(return_value=None)
    llm_executor = MagicMock()
    llm_executor.execute_llm = AsyncMock()
    prompt_resolver = MagicMock()
    prompt_resolver.resolve = AsyncMock(
        return_value=ResolvedPrompt(prompt_text="x", output_schema={}, input_schema={})
    )
    node = ToolResolver(
        tracer=tracer,
        llm_executor=llm_executor,
        prompt_resolver=prompt_resolver,
        agent_runtime_resolver=None,
        completion_budget_policy=None,
        tool_catalog_retriever=retriever,
        agents_repository=agents_repo,
        tool_catalog_indexer=None,
    )

    context = _make_context(input_payload={"user_input": "query"})

    result = await node.execute(context)

    assert result.data["result"] == []
    retriever.retrieve_candidates.assert_not_called()
    llm_executor.execute_llm.assert_not_called()


@pytest.mark.asyncio
async def test_tool_selection_updates_context_available_tools_with_rag_candidates():
    tool = AvailableTool(
        name="tool-keep",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        retrieval_score=0.9,
    )
    rag_config_id = uuid.uuid4()

    node, _, _, _ = _build_tool_selection_node(
        retriever_return=([tool], []),
        rag_config_id=rag_config_id,
    )

    context = _make_context(input_payload={"user_input": "do something"})

    await node.execute(context)

    assert len(context.available_tools) == 1
    assert context.available_tools[0].name == "tool-keep"


@pytest.mark.asyncio
async def test_tool_selection_writes_next_state_from_llm():
    tool = AvailableTool(
        name="tool-1",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        retrieval_score=0.8,
    )
    rag_config_id = uuid.uuid4()

    node, _, _, _ = _build_tool_selection_node(
        retriever_return=([tool], []),
        rag_config_id=rag_config_id,
    )

    context = _make_context(input_payload={"user_input": "find tool"})

    result = await node.execute(context)

    assert result.next_state is not None
    assert NodeType.ToolResolver in result.next_state


@pytest.mark.asyncio
async def test_tool_selection_indexes_when_llm_confidence_above_threshold():
    tool = AvailableTool(
        name="createExpense",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        method="POST",
        retrieval_score=0.4,
    )
    rag_config_id = uuid.uuid4()
    tool_catalog_indexer = MagicMock()
    tool_catalog_indexer.index_document = AsyncMock(return_value=None)

    node, _, _, _ = _build_tool_selection_node(
        retriever_return=([tool], []),
        rag_config_id=rag_config_id,
        tool_catalog_indexer=tool_catalog_indexer,
    )

    context = _make_context(input_payload={"user_input": "paguei no cartao"})

    await node.execute(context)

    tool_catalog_indexer.index_document.assert_called_once()


@pytest.mark.asyncio
async def test_tool_selection_skips_index_when_llm_confidence_below_threshold():
    tool = AvailableTool(
        name="createExpense",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        method="POST",
        retrieval_score=0.4,
    )
    rag_config_id = uuid.uuid4()
    llm_output = {
        "result": [
            {
                "intent_type": "command",
                "selected_tool": {
                    "name": tool.name,
                    "tool_config_id": str(tool.tool_config_id),
                },
                "confidence": 0.5,
            }
        ]
    }
    tool_catalog_indexer = MagicMock()
    tool_catalog_indexer.index_document = AsyncMock(return_value=None)

    node, _, _, _ = _build_tool_selection_node(
        retriever_return=([tool], []),
        rag_config_id=rag_config_id,
        llm_output=llm_output,
        tool_catalog_indexer=tool_catalog_indexer,
    )

    context = _make_context(input_payload={"user_input": "paguei no cartao"})

    await node.execute(context)

    tool_catalog_indexer.index_document.assert_not_called()


@pytest.mark.asyncio
async def test_tool_selection_semantic_retrieval_instrumentation():
    tool = AvailableTool(
        name="createExpense",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        method="POST",
        retrieval_score=0.92,
    )
    other = AvailableTool(
        name="deleteExpense",
        tool_id=uuid.uuid4(),
        tool_config_id=uuid.uuid4(),
        method="DELETE",
        retrieval_score=0.61,
    )
    evidence = [{"tool_config_id": str(tool.tool_config_id), "score": 0.92}]
    tracer = _FakeTracer()
    rag_config_id = uuid.uuid4()
    node, _, _, _ = _build_tool_selection_node(
        retriever_return=([tool, other], evidence),
        rag_config_id=rag_config_id,
        tracer=tracer,
    )
    context = _make_context(input_payload={"user_input": "paguei no cartao"})

    await node.execute(context)

    retrieval_record = next(
        r
        for r in tracer.records
        if r["name"] == "domain.execution.nodes.tool_selection.semantic_retrieval"
    )
    execute_record = next(
        r
        for r in tracer.records
        if r["name"] == "domain.execution.nodes.tool_selection.execute"
    )
    assert retrieval_record["output"]["candidate_count"] == 2
    assert retrieval_record["output"]["evidence"] == evidence
    assert retrieval_record["output"]["selected_tools"][0]["retrieval_score"] == 0.92
    assert execute_record["output"]["selection_mode"] == "rag_with_llm"
    assert execute_record["output"]["reason"] == "llm_selection"


@pytest.mark.asyncio
async def test_tool_selection_empty_when_rag_returns_no_candidates():
    rag_config_id = uuid.uuid4()
    node, retriever, _, llm_executor = _build_tool_selection_node(
        retriever_return=([], []),
        rag_config_id=rag_config_id,
    )
    context = _make_context(input_payload={"user_input": "x"})

    result = await node.execute(context)

    assert result.data["result"] == []
    llm_executor.execute_llm.assert_not_called()


def test_node_attributes():
    assert ToolResolver.node_type == "ToolResolver"
    assert ToolResolver.side_effect is False
    assert ToolResolver.deterministic is False
