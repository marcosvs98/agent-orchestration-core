"""BDD: EdgeEvaluator — compile + evaluate edge conditions."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

pytestmark = pytest.mark.bdd

from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from exceptions.service_exceptions import DomainValidationException

FEATURE = Path(__file__).parent / "features" / "edge_evaluator.feature"

scenarios(str(FEATURE))


@given("the edge condition checks string equality on status")
def _cond_status_eq(bdd):
    bdd.condition_text = 'status == "ok"'


@given("the edge condition uses HasAny on tag lists")
def _cond_has_any(bdd):
    bdd.condition_text = 'HasAny(tags, ["a", "b"])'


@given(parsers.parse('a compiled condition from "{expr}"'))
def _compile_given_expr(bdd, expr):
    bdd.compiled_condition = EdgeEvaluator.compile_condition(expr)


@when("we evaluate on matching status context")
def _eval_status_ok(bdd):
    bdd.evaluation_result = EdgeEvaluator.is_true(
        bdd.condition_text,
        {"status": "ok"},
    )


@when("we evaluate on overlapping tags context")
def _eval_tags(bdd):
    bdd.evaluation_result = EdgeEvaluator.is_true(
        bdd.condition_text,
        {"tags": ["x", "a"]},
    )


@when(parsers.parse('compiling the invalid edge condition "{text}"'))
def _compile_invalid(bdd, text):
    bdd.compile_error = None
    try:
        EdgeEvaluator.compile_condition(text)
    except DomainValidationException as exc:
        bdd.compile_error = exc


@when("identifiers are collected from the compiled tree")
def _collect_ids(bdd):
    bdd.collected_ids = EdgeEvaluator.collect_identifiers(bdd.compiled_condition)


@then("the result is true")
def _assert_true(bdd):
    assert bdd.evaluation_result is True


@then("compile fails with domain validation")
def _assert_compile_fail(bdd):
    assert bdd.compile_error is not None
    assert bdd.compile_error.message == "edge_condition_invalid"


@then(parsers.parse('"{name}" is among the collected identifiers'))
def _assert_id_present(bdd, name):
    assert name in bdd.collected_ids
