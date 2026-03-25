import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.execution.services.graph_runtime.nodes.intent_classifier import (
    IntentClassifier,
)
from domain.execution.services.graph_runtime.nodes.intent_examples_retriever import (
    IntentSemanticMatch,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    IntentType,
    NodeExecutionStatus,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType


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
        current_node_id=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


def _fallback_result(intent_type: str, confidence: float) -> NodeResult:
    payload = {
        "result": [
            {
                "intent_type": intent_type,
                "confidence": confidence,
                "priority": 1,
            }
        ],
        "overall_confidence": confidence,
    }
    return NodeResult(
        node=NodeType.IntentClassifier,
        status=NodeExecutionStatus.SUCCESS,
        data=payload,
        next_state={NodeType.IntentClassifier.value: payload},
    )


def _build_node(
    *,
    retriever_match: IntentSemanticMatch | None,
    fallback_result: NodeResult | None,
    rag_config_id: uuid.UUID | None,
):
    tracer = _FakeTracer()
    retriever = MagicMock()
    retriever.retrieve_best_match = AsyncMock(return_value=retriever_match)
    agents_repository = MagicMock()
    agents_repository.resolve_effective_rag_config_id_for_node = AsyncMock(
        return_value=rag_config_id
    )
    llm_fallback = MagicMock()
    llm_fallback.execute = AsyncMock(return_value=fallback_result)
    node = IntentClassifier(
        tracer=tracer,
        agents_repository=agents_repository,
        intent_examples_retriever=retriever,
        llm_fallback=llm_fallback,
    )
    return node, retriever, llm_fallback


@pytest.mark.asyncio
async def test_intent_detection_returns_semantic_result_when_above_threshold():
    node, retriever, llm_fallback = _build_node(
        retriever_match=IntentSemanticMatch(
            intent_type=IntentType.COMMAND,
            score=0.91,
            metadata={"intent_type": "command"},
        ),
        fallback_result=_fallback_result("conversation", 0.2),
        rag_config_id=uuid.uuid4(),
    )
    context = _make_context(input_payload={"user_input": "pagar conta"})

    result = await node.execute(
        context, config={"confidence_threshold": 0.85, "top_k": 1}
    )

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["result"][0]["intent_type"] == "command"
    assert result.data["overall_confidence"] == 0.91
    llm_fallback.execute.assert_not_called()
    retriever.retrieve_best_match.assert_awaited_once()


@pytest.mark.asyncio
async def test_intent_detection_calls_fallback_when_below_threshold():
    fallback_result = _fallback_result("query", 0.77)
    node, _, llm_fallback = _build_node(
        retriever_match=IntentSemanticMatch(
            intent_type=IntentType.COMMAND,
            score=0.33,
            metadata={"intent_type": "command"},
        ),
        fallback_result=fallback_result,
        rag_config_id=uuid.uuid4(),
    )
    context = _make_context(input_payload={"user_input": "mensagem ambígua"})

    result = await node.execute(
        context, config={"confidence_threshold": 0.85, "top_k": 1}
    )

    assert result.data["result"][0]["intent_type"] == "query"
    llm_fallback.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_intent_detection_calls_fallback_when_rag_config_is_missing():
    fallback_result = _fallback_result("conversation", 0.66)
    node, retriever, llm_fallback = _build_node(
        retriever_match=IntentSemanticMatch(
            intent_type=IntentType.QUERY,
            score=0.99,
            metadata={"intent_type": "query"},
        ),
        fallback_result=fallback_result,
        rag_config_id=None,
    )
    context = _make_context(input_payload={"user_input": "qual meu saldo?"})

    result = await node.execute(context)

    assert result.data["result"][0]["intent_type"] == "conversation"
    retriever.retrieve_best_match.assert_not_called()
    llm_fallback.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_intent_detection_reads_top_k_from_node_config():
    node, retriever, llm_fallback = _build_node(
        retriever_match=IntentSemanticMatch(
            intent_type=IntentType.QUERY,
            score=0.9,
            metadata={"intent_type": "query"},
        ),
        fallback_result=_fallback_result("command", 0.4),
        rag_config_id=uuid.uuid4(),
    )
    context = _make_context(input_payload={"user_input": "consultar saldo"})

    result = await node.execute(
        context, config={"confidence_threshold": 0.8, "top_k": 3}
    )

    assert result.data["result"][0]["intent_type"] == "query"
    assert retriever.retrieve_best_match.await_args.kwargs["top_k"] == 3
    llm_fallback.execute.assert_not_called()


@pytest.mark.asyncio
async def test_intent_detection_uses_heuristic_for_empty_input():
    node, retriever, llm_fallback = _build_node(
        retriever_match=None,
        fallback_result=_fallback_result("query", 0.4),
        rag_config_id=uuid.uuid4(),
    )
    context = _make_context(input_payload={"user_input": "   "})

    result = await node.execute(context)

    assert result.data["result"][0]["intent_type"] == "conversation"
    assert result.data["overall_confidence"] == 1.0
    retriever.retrieve_best_match.assert_not_called()
    llm_fallback.execute.assert_not_called()
