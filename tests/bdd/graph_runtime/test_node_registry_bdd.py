"""BDD: NodeRegistry resolves node implementations with injected dependencies."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

pytestmark = pytest.mark.bdd

from domain.execution.services.graph_runtime.registry import NodeRegistry

FEATURE = Path(__file__).parent / "features" / "node_registry.feature"

scenarios(str(FEATURE))


@given("a node registry without LLM executor")
def _reg_no_llm(tracer, bdd):
    bdd.registry = NodeRegistry(tracer=tracer)


@given("a node registry without moderation provider")
def _reg_no_mod(tracer, bdd):
    bdd.registry = NodeRegistry(tracer=tracer, llm_moderation_provider=None)


@given("a node registry with LLM stack mocks")
def _reg_llm(tracer, bdd):
    bdd.registry = NodeRegistry(
        tracer=tracer,
        llm_executor=MagicMock(),
        prompt_resolver=MagicMock(),
    )


@when(parsers.parse('resolving "{node_type}"'))
def _resolve_and_instantiate(bdd, node_type):
    cls = bdd.registry.resolve(node_type)
    bdd.resolve_error = None
    bdd.resolved_instance = None
    try:
        bdd.resolved_instance = cls()
    except ValueError as exc:
        bdd.resolve_error = exc


@then("resolution raises because required dependencies are missing")
def _assert_resolve_error(bdd):
    assert bdd.resolve_error is not None


@then("the resolved class can be instantiated")
def _assert_instance(bdd):
    assert bdd.resolved_instance is not None
