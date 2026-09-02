import contextlib

import pytest

from domain.execution.services.graph_runtime.nodes import (
    ContextSummarizer,
    HumanFallback,
    IntentClassifier,
    QueryClarifier,
    ResponseBuilder,
    ToolExecutor,
    ToolInputFiller,
    ToolResolver,
)
from domain.execution.services.graph_runtime.registry import NodeRegistry


class _FakeTracer:
    def observe(self, *, as_type=None, name=None, input=None, metadata=None):
        return contextlib.nullcontext()


def test_node_registry_resolves_valid_node_types():
    registry = NodeRegistry(tracer=_FakeTracer())

    intent_cls = registry.resolve("ToolResolver")
    assert intent_cls is not None
    assert issubclass(intent_cls, ToolResolver)

    tool_cls = registry.resolve("ToolExecutor")
    assert tool_cls is not None
    assert issubclass(tool_cls, ToolExecutor)

    clarification_cls = registry.resolve("QueryClarifier")
    assert clarification_cls is not None
    assert issubclass(clarification_cls, QueryClarifier)

    param_cls = registry.resolve("ToolInputFiller")
    assert param_cls is not None
    assert issubclass(param_cls, ToolInputFiller)

    response_cls = registry.resolve("ResponseBuilder")
    assert response_cls is not None
    assert issubclass(response_cls, ResponseBuilder)
    fallback_cls = registry.resolve("HumanFallback")
    assert fallback_cls is not None
    assert issubclass(fallback_cls, HumanFallback)


def test_node_registry_returns_none_for_unknown_type():
    registry = NodeRegistry(tracer=_FakeTracer())
    assert registry.resolve("UnknownNodeType") is None
    assert registry.resolve("") is None


def test_node_registry_injects_dependencies():
    mock_orchestrator = object()
    mock_repository = object()

    registry = NodeRegistry(
        tracer=_FakeTracer(),
        tool_orchestrator=mock_orchestrator,
        execution_repository=mock_repository,
    )

    tool_cls = registry.resolve("ToolExecutor")
    assert tool_cls is not None

    instance = tool_cls()
    assert instance.tool_orchestrator is mock_orchestrator
    assert instance.execution_repository is mock_repository


def test_node_registry_resolves_context_summarizer():
    registry = NodeRegistry(tracer=_FakeTracer())
    summarize_cls = registry.resolve(ContextSummarizer.node_type)
    assert summarize_cls is not None
    assert issubclass(summarize_cls, ContextSummarizer)


def test_node_registry_resolves_intent_classifier():
    registry = NodeRegistry(tracer=_FakeTracer())
    intent_cls = registry.resolve(IntentClassifier.node_type)
    assert intent_cls is not None
    assert issubclass(intent_cls, IntentClassifier)


@pytest.mark.parametrize(
    "node_type",
    [
        ContextSummarizer.node_type,
        HumanFallback.node_type,
        IntentClassifier.node_type,
        QueryClarifier.node_type,
        ResponseBuilder.node_type,
        ToolExecutor.node_type,
        ToolInputFiller.node_type,
    ],
)
def test_node_registry_resolved_classes_are_constructible(node_type):
    registry = NodeRegistry(
        tracer=_FakeTracer(),
        llm_executor=object(),
        prompt_resolver=object(),
        tool_orchestrator=object(),
        execution_repository=object(),
        memory_write_service=object(),
        agent_runtime_resolver=object(),
        completion_budget_policy=object(),
        tool_catalog_retriever=object(),
        agents_repository=object(),
        llm_moderation_provider=object(),
        human_sla_service=object(),
    )

    node_cls = registry.resolve(node_type)
    assert node_cls is not None

    instance = node_cls()
    assert callable(instance.execute)
