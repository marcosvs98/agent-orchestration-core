"""BDD: ExecutionPlan value object."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

pytestmark = pytest.mark.bdd

from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan

FEATURE = Path(__file__).parent / "features" / "execution_plan.feature"

scenarios(str(FEATURE))


@given("a minimal execution plan fixture")
def _minimal_plan(bdd):
    bdd.plan = ExecutionPlan(
        start_node_id="s1",
        ordered_nodes=["s1"],
        adjacency_map={},
        terminal_nodes={"s1"},
        structural_hash="bdd-plan-hash",
        nodes={"s1": {"type": "ResponseBuilder"}},
        available_tools=[],
    )


@when("the plan is serialized with model_dump mode json")
def _dump(bdd):
    bdd.plan_payload = bdd.plan.model_dump(mode="json")


@then("the start node id is preserved in the payload")
def _assert_start(bdd):
    assert bdd.plan_payload["start_node_id"] == "s1"
