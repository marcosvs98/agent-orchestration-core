import contextlib
from typing import Any, Dict, List

import pytest

from domain.execution.services.graph_runtime.graph_compiler import GraphCompiler
from exceptions.service_exceptions import DomainValidationException


class _NullTracer:
    def observe(self, *, as_type, name, input, metadata=None):
        return contextlib.nullcontext()


MODERATION = "1dd82f72-c58a-4724-a3fd-ec93c17f10d0"
EXECUTOR = "3ebe4bb6-0b23-4e8b-8bb0-b132c49af991"
ERROR_HANDLER = "108d6251-6400-4a89-b6f9-39bbf887b18a"
RESPONSE = "b1b86ffc-707d-4ae2-931b-1d69b2f2ae2f"


def _edge(from_node: str, to_node: str, kind: str = "NORMAL") -> Dict[str, Any]:
    return {
        "from_node": from_node,
        "to_node": to_node,
        "condition": "1==1",
        "edge_kind": kind,
        "compiled_condition": ["always"],
    }


def _snapshot(edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "start_node": MODERATION,
        "nodes": {
            MODERATION: {"type": "ContentModeration"},
            EXECUTOR: {"type": "ToolExecutor"},
            ERROR_HANDLER: {"type": "ToolErrorHandlerNode"},
            RESPONSE: {"type": "ResponseBuilder"},
        },
        "edges": edges,
    }


def _retry_loop_edges() -> List[Dict[str, Any]]:
    return [
        _edge(MODERATION, EXECUTOR),
        _edge(EXECUTOR, ERROR_HANDLER),
        _edge(EXECUTOR, RESPONSE),
        _edge(ERROR_HANDLER, EXECUTOR, kind="LOOP"),
        _edge(ERROR_HANDLER, RESPONSE),
    ]


def test_retry_loop_compiles_even_when_the_loop_node_sorts_before_the_start_node():
    compiler = GraphCompiler(tracer=_NullTracer())

    plan = compiler.compile(_snapshot(_retry_loop_edges()), structural_hash="h")

    assert plan.start_node_id == MODERATION
    assert ERROR_HANDLER < MODERATION


def test_loop_validation_does_not_depend_on_node_id_ordering():
    compiler = GraphCompiler(tracer=_NullTracer())
    edges = _retry_loop_edges()

    forward = compiler.compile(_snapshot(edges), structural_hash="h")
    reordered = compiler.compile(_snapshot(list(reversed(edges))), structural_hash="h")

    assert set(forward.adjacency_map) == set(reordered.adjacency_map)


def test_unmarked_cycle_reachable_from_start_is_still_rejected():
    compiler = GraphCompiler(tracer=_NullTracer())
    edges = [
        _edge(MODERATION, EXECUTOR),
        _edge(EXECUTOR, ERROR_HANDLER),
        _edge(ERROR_HANDLER, EXECUTOR),
        _edge(EXECUTOR, RESPONSE),
    ]

    with pytest.raises(DomainValidationException) as exc:
        compiler.compile(_snapshot(edges), structural_hash="h")

    assert exc.value.message == "cycle_not_marked_loop"


def test_unreachable_node_is_rejected_before_loop_validation():
    compiler = GraphCompiler(tracer=_NullTracer())
    edges = [
        _edge(MODERATION, EXECUTOR),
        _edge(EXECUTOR, RESPONSE),
        _edge(ERROR_HANDLER, EXECUTOR, kind="LOOP"),
    ]

    with pytest.raises(DomainValidationException) as exc:
        compiler.compile(_snapshot(edges), structural_hash="h")

    assert exc.value.message == "unreachable_nodes"
