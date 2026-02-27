import pytest

from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    ParamExtractionNode,
    ResponseComposer,
    ToolExecutionNode,
    ToolSelectionNode,
)
from domain.execution.services.graph_runtime.registry import NodeRegistry


class _FakeTracer:
    def observe(self, *, as_type=None, name=None, input=None, metadata=None):
        return __import__("contextlib").nullcontext()


def test_node_registry_resolves_valid_node_types():
    registry = NodeRegistry(tracer=_FakeTracer())

    intent_cls = registry.resolve("ToolSelectionNode")
    assert intent_cls is not None
    assert issubclass(intent_cls, ToolSelectionNode)

    tool_cls = registry.resolve("ToolExecutionNode")
    assert tool_cls is not None
    assert issubclass(tool_cls, ToolExecutionNode)

    clarification_cls = registry.resolve("ClarificationNode")
    assert clarification_cls is not None
    assert issubclass(clarification_cls, ClarificationNode)

    param_cls = registry.resolve("ParamExtractionNode")
    assert param_cls is not None
    assert issubclass(param_cls, ParamExtractionNode)

    response_cls = registry.resolve("ResponseComposer")
    assert response_cls is not None
    assert issubclass(response_cls, ResponseComposer)
    fallback_cls = registry.resolve("FallbackNodeSLA")
    assert fallback_cls is not None
    assert fallback_cls == FallbackNode


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

    tool_cls = registry.resolve("ToolExecutionNode")
    assert tool_cls is not None

    instance = tool_cls()
    assert instance.tool_orchestrator is mock_orchestrator
    assert instance.execution_repository is mock_repository
