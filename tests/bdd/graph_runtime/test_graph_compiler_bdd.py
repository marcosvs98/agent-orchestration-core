"""BDD: GraphCompiler — flow snapshot → ExecutionPlan."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.bdd
from pytest_bdd import given, parsers, scenarios, then, when

from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.execution.services.graph_runtime.graph_compiler import GraphCompiler
from domain.flows.schemas.graph import EdgeKind
from domain.prompts.schemas.prompt import NodeType
from exceptions.service_exceptions import DomainValidationException

FEATURE = Path(__file__).parent / "features" / "graph_compiler.feature"

scenarios(str(FEATURE))


def _truthy_condition() -> object:
    return EdgeEvaluator.compile_condition("1 == 1")


@given("a linear two-node snapshot with compiled edges")
def _linear_snapshot(bdd):
    c = _truthy_condition()
    bdd.snapshot = {
        "start_node": "n1",
        "nodes": {
            "n1": {"type": NodeType.IntentClassifier.value},
            "n2": {"type": NodeType.ResponseBuilder.value},
        },
        "edges": [
            {
                "from_node": "n1",
                "to_node": "n2",
                "compiled_condition": c,
                "edge_kind": EdgeKind.NORMAL.value,
            },
        ],
    }


@given("a snapshot whose start_node is not in nodes")
def _bad_start(bdd):
    c = _truthy_condition()
    bdd.snapshot = {
        "start_node": "missing",
        "nodes": {
            "n1": {"type": NodeType.ResponseBuilder.value},
        },
        "edges": [
            {
                "from_node": "n1",
                "to_node": "n1",
                "compiled_condition": c,
                "edge_kind": EdgeKind.LOOP.value,
            },
        ],
    }


@given("a snapshot with nodes but no edges")
def _no_edges(bdd):
    bdd.snapshot = {
        "start_node": "n1",
        "nodes": {
            "n1": {"type": NodeType.ResponseBuilder.value},
        },
        "edges": [],
    }


@given("a snapshot with only non-terminal node types")
def _no_terminal(bdd):
    c = _truthy_condition()
    bdd.snapshot = {
        "start_node": "n1",
        "nodes": {
            "n1": {"type": NodeType.IntentClassifier.value},
            "n2": {"type": NodeType.IntentClassifier.value},
        },
        "edges": [
            {
                "from_node": "n1",
                "to_node": "n2",
                "compiled_condition": c,
                "edge_kind": EdgeKind.NORMAL.value,
            },
        ],
    }


@given("a snapshot with an edge missing compiled_condition")
def _missing_compiled(bdd):
    bdd.snapshot = {
        "start_node": "n1",
        "nodes": {
            "n1": {"type": NodeType.IntentClassifier.value},
            "n2": {"type": NodeType.ResponseBuilder.value},
        },
        "edges": [
            {
                "from_node": "n1",
                "to_node": "n2",
                "compiled_condition": None,
                "edge_kind": EdgeKind.NORMAL.value,
            },
        ],
    }


@given("a snapshot with an isolated unreachable node")
def _unreachable(bdd):
    c = _truthy_condition()
    bdd.snapshot = {
        "start_node": "n1",
        "nodes": {
            "n1": {"type": NodeType.IntentClassifier.value},
            "n2": {"type": NodeType.ResponseBuilder.value},
            "n3": {"type": NodeType.IntentClassifier.value},
        },
        "edges": [
            {
                "from_node": "n1",
                "to_node": "n2",
                "compiled_condition": c,
                "edge_kind": EdgeKind.NORMAL.value,
            },
        ],
    }


@given("a two-node cycle using only NORMAL edges")
def _cycle_normal(bdd):
    c = _truthy_condition()
    bdd.snapshot = {
        "start_node": "n1",
        "nodes": {
            "n1": {"type": NodeType.IntentClassifier.value},
            "n2": {"type": NodeType.ResponseBuilder.value},
        },
        "edges": [
            {
                "from_node": "n1",
                "to_node": "n2",
                "compiled_condition": c,
                "edge_kind": EdgeKind.NORMAL.value,
            },
            {
                "from_node": "n2",
                "to_node": "n1",
                "compiled_condition": c,
                "edge_kind": EdgeKind.NORMAL.value,
            },
        ],
    }


@given("a two-node cycle with the back-edge marked LOOP")
def _cycle_loop(bdd):
    c = _truthy_condition()
    bdd.snapshot = {
        "start_node": "n1",
        "nodes": {
            "n1": {"type": NodeType.IntentClassifier.value},
            "n2": {"type": NodeType.ResponseBuilder.value},
        },
        "edges": [
            {
                "from_node": "n1",
                "to_node": "n2",
                "compiled_condition": c,
                "edge_kind": EdgeKind.NORMAL.value,
            },
            {
                "from_node": "n2",
                "to_node": "n1",
                "compiled_condition": c,
                "edge_kind": EdgeKind.LOOP.value,
            },
        ],
    }


@when("the graph compiler compiles the snapshot")
def _compile_ok(bdd, tracer):
    gc = GraphCompiler(tracer)
    bdd.plan = gc.compile(bdd.snapshot, bdd.structural_hash)
    bdd.error = None


@when("the graph compiler compiles the snapshot expecting failure")
def _compile_fail(bdd, tracer):
    gc = GraphCompiler(tracer)
    bdd.plan = None
    try:
        gc.compile(bdd.snapshot, bdd.structural_hash)
    except DomainValidationException as exc:
        bdd.error = exc
    else:
        raise AssertionError("expected DomainValidationException")


@then('the plan start node is "n1"')
def _assert_start(bdd):
    assert bdd.plan is not None
    assert bdd.plan.start_node_id == "n1"


@then('the plan lists "n2" as a terminal node')
def _assert_terminal(bdd):
    assert bdd.plan is not None
    assert "n2" in bdd.plan.terminal_nodes


@then("the structural hash is stored on the plan")
def _assert_hash(bdd):
    assert bdd.plan is not None
    assert bdd.plan.structural_hash == bdd.structural_hash


@then(parsers.parse('validation fails with message "{msg}"'))
def _assert_validation_msg(bdd, msg):
    assert bdd.error is not None
    assert bdd.error.message == msg
