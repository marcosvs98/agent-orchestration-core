"""Shared fixtures for graph_runtime BDD scenarios (isolated, no DB)."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given

from domain.execution.ports.runtime_tracer import RuntimeTracerPort


@given("a runtime tracer stub")
def _runtime_tracer_stub(tracer):
    """Background step: tracer mock from fixture."""
    return tracer


@pytest.fixture
def bdd() -> SimpleNamespace:
    """Mutable context passed between Given / When / Then steps."""
    return SimpleNamespace(
        snapshot=None,
        structural_hash="bdd-structural-hash",
        plan=None,
        error=None,
        evaluation_result=None,
        compiled_condition=None,
        registry=None,
        resolved_class=None,
        node_instance=None,
        tool_error_result=None,
    )


@pytest.fixture
def tracer() -> MagicMock:
    t = MagicMock(spec=RuntimeTracerPort)
    h = MagicMock()
    h.success = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(h)
    return t
